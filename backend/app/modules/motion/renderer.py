"""The first local rendering engine for the Video Factory: turns one still
image + a MotionPlan into an MP4 clip via a local ffmpeg Ken-Burns pipeline
(scale/pan/zoom/rotate). No AI video generation, no cloud service -- only
ffmpeg, already a bundled dependency of this app (see
app/main.py's `_prepend_bundled_ffmpeg_to_path`).

Unlike app/modules/motion/service.py (deliberately rendering-free -- see its
own docstring), this file is exactly the "future rendering layer" that
service.py and schemas.py both said does not belong inside their files. It
still lives in this module (not a new top-level module) because it needs
`MotionPlan`/`Easing`/etc. from schemas.py, and per app/modules/README.md a
module may freely use its own files -- only importing *another* module is
forbidden. This file imports nothing from app.modules.beat/asset/
composition/ai/scene_cutter/video_composer.

No shared ffmpeg wrapper exists anywhere in this codebase (confirmed in
docs/features/video_factory_architecture.md's reconnaissance) --
`app/modules/scene_cutter/service.py` and `app/modules/video_composer/service.py`
each already run their own `subprocess.run(["ffmpeg"/"ffprobe", ...])`
calls with no shared helper between them. This file follows that same
established "copy the pattern, don't invent a cross-module wrapper"
convention rather than introducing a new one.

The renderer is preset-agnostic: it never branches on `MotionPlan.preset`.
It only reads the resolved numeric fields (scale/position/rotation/easing),
so a single ffmpeg pipeline covers all 9 presets in
docs/features/21-motion-domain-presets.md (and any future preset) for
free, rather than needing nine hand-written special cases.
"""

import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import FileOperationError, RenderCancelled, ValidationError
from app.modules.motion.schemas import MAX_DURATION, MIN_DURATION, Easing, MotionPlan

logger = logging.getLogger(__name__)

# "The project resolution"/"the configured FPS" (per this task's brief) have
# no existing home in app.core.config.Settings -- nothing in this codebase
# has needed a video-output-format setting before now. Rather than bolt a
# Video-Factory-specific setting onto shared core config for a renderer
# nothing wires up to an endpoint yet, these are named, documented defaults
# a caller can override per call; when a real orchestrator/endpoint is
# built on top of this, *that* integration point can decide whether to
# source these from Settings, a request, or a Composition Scene's own
# OutputFormat (see docs/features/22-composition-contract.md).
DEFAULT_FPS = 30.0
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920

# zoompan crops at integer pixel offsets of its *input* frame, so zooming or
# panning directly on a modestly-sized source image produces visibly
# jittery motion. Pre-scaling the source up substantially first gives it
# enough sub-output-pixel precision to look smooth -- a standard,
# widely-documented zoompan technique, not specific to this app.
#
# Multiplies the *target* width/height (not a fixed absolute size) so the
# prescaled canvas always has the exact same aspect ratio as the output.
# This matters beyond resolution: zoompan crops a window whose aspect
# ratio always equals its input's aspect ratio (iw/ih), regardless of
# zoom level, then scales that window to `s=WxH`. If the prescaled input's
# aspect ratio doesn't already match width:height, every single frame
# gets stretched non-uniformly -- a real bug found during this task's own
# manual verification (a circle rendered as an ellipse) -- see
# docs/features/34-local-motion-renderer.md.
_PRESCALE_FACTOR = 6

# Task 23 -- see build_filter_graph's own docstring for the real,
# pre-existing bug this fixes: ffmpeg's image2 demuxer decodes a
# `-loop 1 -i` single-image source at a fixed internal rate, empirically
# confirmed (via real pixel-sampled rendered output, not documentation) to
# be ~25fps regardless of any `-framerate` flag or the caller's requested
# output fps. zoompan's own `d`/`on` progression must be computed against
# THIS rate, never the caller's output fps, or the pan/zoom animation
# finishes early and visibly freezes for the remainder of the clip whenever
# output fps < 25 (which is most of this app's own real usage -- see
# DEFAULT_FPS below, and every test fixture using a lower fps for fast
# rendering).
_ZOOMPAN_REFERENCE_FPS = 25.0

# -nostdin: ffmpeg reads stdin by default for interactive key commands
# (e.g. "press q to stop"); run non-interactively as a subprocess, an
# inherited/piped stdin that never delivers EOF can make it block
# indefinitely instead of failing fast on a bad input. Confirmed as a real
# hang during this task's own manual testing (a corrupted input file left
# ffmpeg waiting on stdin rather than exiting with an error) -- not a
# theoretical concern. subprocess.run's own stdin=DEVNULL below is a second,
# redundant guard against the same failure mode.
_FFMPEG_PREFIX = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"]


def _apply_easing(progress_expr: str, easing: Easing) -> str:
    """Turn a linear 0..1 progress expression into an eased one, in ffmpeg's
    own expression syntax (so it's evaluated once per frame by ffmpeg
    itself, not precomputed in Python). Polynomial (smoothstep) rather than
    cosine-based ease-in-out, since it needs only +-*/pow -- no dependency
    on ffmpeg's eval supporting a PI-based trig constant for this part.
    """
    p = f"({progress_expr})"
    if easing == Easing.LINEAR:
        return p
    if easing == Easing.EASE_IN:
        return f"pow({p},2)"
    if easing == Easing.EASE_OUT:
        return f"(1-pow(1-{p},2))"
    return f"(3*pow({p},2)-2*pow({p},3))"  # ease_in_out (cubic smoothstep)


def _lerp(start: float, end: float, progress_expr: str) -> str:
    return f"({start}+({end}-{start})*({progress_expr}))"


def _is_static(motion_plan: MotionPlan) -> bool:
    return (
        motion_plan.scale.start == motion_plan.scale.end == 1.0
        and motion_plan.position.x_start == motion_plan.position.x_end
        and motion_plan.position.y_start == motion_plan.position.y_end
        and motion_plan.rotation.start == motion_plan.rotation.end == 0.0
    )


def build_filter_graph(
    motion_plan: MotionPlan, duration: float, fps: float, width: int, height: int,
    focal_x: float = 0.5, focal_y: float = 0.5,
) -> str:
    """Pure function: builds the `-vf` filter graph string for one motion
    render. No I/O, no subprocess -- safe and fast to unit test directly.

    `focal_x`/`focal_y` (Task 23 -- see docs/features/49-local-motion-engine.md
    section 32) only affect the STATIC/no-movement crop below -- every other
    preset already bakes the focal point into its own zoompan x/y expression
    via `motion_plan.position` (see app.modules.motion.service.build_motion_plan),
    so this function never needs them for the zoompan branch.

    Real bug found and fixed during Task 23's own manual verification
    (see docs/features/49-local-motion-engine.md's own "Problems"/verification
    section): zoompan's `on` counter advances once per frame *decoded from
    the input*, and ffmpeg's image2 demuxer for a single `-loop 1 -i`
    source decodes at a fixed internal rate empirically confirmed (via real
    rendered-output pixel sampling across many fps/duration combinations)
    to be ~25fps *regardless* of any `-framerate` flag or the caller's
    requested output `fps` -- a pre-existing bug (present since this
    renderer was first built, well before Task 23) that had nothing to do
    with the Task 23 changes in this file. Computing `d`/the easing
    denominator from the *output* fps (e.g. 10, 24, 30 -- whatever a caller
    asked for) meant the pan/zoom animation reached its own endpoint after
    only `output_fps/25` of the clip's real duration whenever output_fps <
    25, then visibly froze in place for the remainder -- a real, previously
    unnoticed video-quality defect. `_ZOOMPAN_REFERENCE_FPS` decouples the
    zoompan cycle from the caller's requested output fps entirely; the
    trailing `fps={fps}` stage below still produces the exact frame rate a
    caller asked for, resampled from an already-smooth reference-rate
    sequence rather than a truncated one.
    """
    zoompan_frame_count = max(1, round(duration * _ZOOMPAN_REFERENCE_FPS))

    if _is_static(motion_plan):
        # No scale/position/rotation change at all -- skip zoompan/rotate
        # entirely rather than running a no-op pass through them, the same
        # "skip the redundant filter pass" spirit as
        # video_composer's single-clip merge skip (see
        # docs/features/11-video-composer.md). No zoompan headroom is
        # needed here (nothing pans/zooms), so this scales straight to
        # "cover" the target frame -- force_original_aspect_ratio=increase
        # (fills both dimensions, may overshoot one) + a crop back down to
        # exactly width x height. This is the fix for a real bug (see
        # docs/features/34-local-motion-renderer.md): the previous
        # decrease+pad recipe was "contain", not "cover", and produced
        # visible black bars whenever the source aspect ratio didn't
        # already match the output exactly.
        #
        # A plain `crop=W:H` (no x/y) is ffmpeg's own dead-center crop --
        # kept exactly as-is (not rewritten to an equivalent 0.5/0.5
        # expression) when the focal point is the default center, so a
        # pre-Task-23 caller's filter graph string is byte-identical to
        # before. A real, off-center focal point (section 32: "motion
        # should preserve the focal area") instead crops around it.
        if focal_x == 0.5 and focal_y == 0.5:
            crop_stage = f"crop={width}:{height}"
        else:
            crop_stage = f"crop={width}:{height}:x='(in_w-{width})*{focal_x}':y='(in_h-{height})*{focal_y}'"
        stages = [
            f"scale={width}:{height}:force_original_aspect_ratio=increase",
            crop_stage,
        ]
    else:
        # Cover-crop to the *output's* aspect ratio at high resolution --
        # see _PRESCALE_FACTOR's comment for why this must be the target
        # aspect ratio, not the source's own.
        prescale_width = width * _PRESCALE_FACTOR
        prescale_height = height * _PRESCALE_FACTOR
        stages = [
            f"scale={prescale_width}:{prescale_height}:force_original_aspect_ratio=increase",
            f"crop={prescale_width}:{prescale_height}",
        ]
        on_progress = f"on/{max(zoompan_frame_count - 1, 1)}"
        eased_on = _apply_easing(on_progress, motion_plan.easing)
        zoom_expr = _lerp(motion_plan.scale.start, motion_plan.scale.end, eased_on)
        cx_expr = _lerp(motion_plan.position.x_start, motion_plan.position.x_end, eased_on)
        cy_expr = _lerp(motion_plan.position.y_start, motion_plan.position.y_end, eased_on)
        # Standard zoompan Ken-Burns formula generalized from the common
        # fixed-center recipe (x='iw/2-(iw/zoom/2)') to a time-varying focus
        # point: crop-window top-left = focus_point_px - half_window_size.
        x_expr = f"(iw*({cx_expr})-(iw/zoom/2))"
        y_expr = f"(ih*({cy_expr})-(ih/zoom/2))"
        stages.append(f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={zoompan_frame_count}:s={width}x{height}")

    if motion_plan.rotation.start != 0.0 or motion_plan.rotation.end != 0.0:
        # rotate's own expression syntax uses `t` (seconds elapsed), not
        # zoompan's `on` (output frame index) -- a different filter, a
        # different timeline variable.
        t_progress = f"t/{duration}"
        eased_t = _apply_easing(t_progress, motion_plan.easing)
        angle_deg_expr = _lerp(motion_plan.rotation.start, motion_plan.rotation.end, eased_t)
        angle_rad_expr = f"(({angle_deg_expr})*PI/180)"
        # Rotating a WxH frame in place can reveal its corners; filled with
        # black rather than computing dynamic zoom compensation for that --
        # acceptable for "subtle" rotation angles (see
        # docs/features/23-local-motion-renderer.md), not worth the added
        # trig complexity for a few degrees of tilt.
        stages.append(f"rotate='{angle_rad_expr}':ow={width}:oh={height}:fillcolor=black")

    stages.append("setsar=1")
    stages.append("format=yuv420p")
    stages.append(f"fps={fps}")
    return ",".join(stages)


def build_ffmpeg_command(
    image_path: Path,
    output_path: Path,
    motion_plan: MotionPlan,
    duration: float,
    fps: float,
    width: int,
    height: int,
    focal_x: float = 0.5,
    focal_y: float = 0.5,
) -> list[str]:
    """Pure function: the complete, ready-to-run ffmpeg argv. No I/O, no
    subprocess -- safe and fast to unit test directly.
    """
    filter_graph = build_filter_graph(motion_plan, duration, fps, width, height, focal_x, focal_y)
    return _FFMPEG_PREFIX + [
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-t",
        f"{duration}",
        "-vf",
        filter_graph,
        "-r",
        f"{fps}",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        # A JPEG source decodes as full-range YUV, which makes ffmpeg
        # report the output as "yuvj420p" (yuv420p's full-range variant)
        # instead of plain "yuv420p" even with -pix_fmt yuv420p above --
        # forcing tv/limited range here keeps the reported pixel format
        # identical regardless of whether the source image was a JPEG or a
        # PNG, which is the actual "stable pixel format" requirement.
        "-color_range",
        "tv",
        str(output_path),
    ]


def _probe_image(image_path: Path) -> None:
    """Fail fast with a clear error on a corrupted/non-image file, rather
    than letting ffmpeg's own cryptic filter-stage error surface later.
    """
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0:s=x",
        str(image_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise FileOperationError("ffprobe was not found on PATH -- is it installed/bundled?") from exc

    # A file ffprobe can't decode at all (e.g. a text file renamed .jpg)
    # still exits 0 and prints "0x0" here rather than failing outright --
    # checking for the literal "x" separator is not enough, since "0x0"
    # contains one too. Both dimensions must be real, positive numbers.
    width_str, _, height_str = result.stdout.strip().partition("x")
    try:
        width, height = int(width_str), int(height_str)
    except ValueError:
        width = height = 0

    if result.returncode != 0 or width <= 0 or height <= 0:
        raise FileOperationError(f"Invalid or unreadable image: {image_path}")


def render_motion_clip(
    image_path: Path | str,
    motion_plan: MotionPlan,
    output_path: Path | str,
    *,
    duration: float | None = None,
    fps: float = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    focal_x: float = 0.5,
    focal_y: float = 0.5,
    on_process_start: Callable[[subprocess.Popen], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Render one still image + MotionPlan into an MP4 at `output_path`.

    `focal_x`/`focal_y` (Task 23) only change the STATIC-preset crop
    center (see build_filter_graph) -- every panning/zooming preset
    already has the focal point baked into its own MotionPlan.position
    (see app.modules.motion.service.build_motion_plan), so passing a
    focal point here alongside a non-STATIC motion_plan built with a
    *different* focal point would disagree; callers should build both
    from the same focal point.

    `duration` overrides `motion_plan.duration` when given -- MotionPlan
    can stand alone with its own duration (see
    docs/features/21-motion-domain-presets.md), but a caller driven by a
    Composition Scene has no motion-level duration to read from at all
    (Scene.duration is authoritative there -- see
    docs/features/22-composition-contract.md), so this lets either caller
    shape supply it.

    Output is a silent (no audio track), H.264/yuv420p MP4 at a fixed,
    deterministic duration and frame rate -- meant to be handed to
    app.modules.video_composer's existing, unmodified multi-clip merge
    contract as one of its `files[]` inputs.

    `on_process_start`/`is_cancelled`, if given, support cancelling an
    in-flight render (Task 11 -- see docs/features/38-render-job-hardening.md)
    without this module needing to know anything about jobs, queues, or
    cancellation tokens: `on_process_start` is called with the live
    `subprocess.Popen` right after it's spawned, so a caller can register it
    somewhere it can call `.terminate()` on; `is_cancelled` is polled once,
    only if ffmpeg then exits non-zero, to decide whether that exit was a
    real ffmpeg failure or this function's own process having just been
    terminated by the caller. A `.terminate()`'d process's exit code isn't a
    reliable cancellation signal by itself on Windows (unlike POSIX's
    negative-signal convention, `TerminateProcess`'s exit code is
    indistinguishable from an ordinary ffmpeg error code) -- `is_cancelled`
    is what actually disambiguates the two, raising RenderCancelled instead
    of FileOperationError so a cancelled render is never reported to the
    user as an ffmpeg error.
    """
    image_path = Path(image_path)
    output_path = Path(output_path)
    effective_duration = motion_plan.duration if duration is None else duration

    if not (MIN_DURATION <= effective_duration <= MAX_DURATION):
        raise ValidationError(
            f"duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {effective_duration}"
        )
    if fps <= 0:
        raise ValidationError(f"fps must be > 0, got {fps}")
    if width <= 0 or height <= 0:
        raise ValidationError(f"width/height must both be > 0, got {width}x{height}")
    if width % 2 or height % 2:
        raise ValidationError(f"width/height must both be even (H.264 requirement), got {width}x{height}")

    if not image_path.exists():
        raise FileOperationError(f"Input image not found: {image_path}")
    if not image_path.is_file():
        raise FileOperationError(f"Input image path is not a file: {image_path}")

    if output_path.exists() and output_path.is_dir():
        raise ValidationError(f"output_path must be a file path, not a directory: {output_path}")

    if shutil.which("ffmpeg") is None:
        raise FileOperationError("ffmpeg was not found on PATH -- is it installed/bundled?")
    if shutil.which("ffprobe") is None:
        raise FileOperationError("ffprobe was not found on PATH -- is it installed/bundled?")

    _probe_image(image_path)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise FileOperationError(f"Cannot create output directory {output_path.parent}: {exc}") from exc

    command = build_ffmpeg_command(
        image_path, output_path, motion_plan, effective_duration, fps, width, height, focal_x, focal_y
    )
    logger.info(
        "Rendering motion clip: %s -> %s (preset=%s, duration=%.2fs, %sx%s@%sfps)",
        image_path,
        output_path,
        motion_plan.preset.value,
        effective_duration,
        width,
        height,
        fps,
    )

    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL
        )
    except FileNotFoundError as exc:
        raise FileOperationError("ffmpeg was not found on PATH -- is it installed/bundled?") from exc

    if on_process_start is not None:
        on_process_start(process)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        if is_cancelled is not None and is_cancelled():
            raise RenderCancelled(f"Motion render for {image_path} was cancelled")
        logger.error("ffmpeg failed rendering %s: %s", image_path, stderr[-2000:])
        raise FileOperationError(f"ffmpeg failed to render motion clip: {stderr.strip()[-2000:]}")

    if not output_path.exists():
        raise FileOperationError(f"ffmpeg reported success but produced no output file: {output_path}")

    return output_path


# -- Existing-video Beat assets (Task 23 sections 12/15) --------------------
#
# An image becomes a clip via zoompan/rotate (render_motion_clip above); an
# already-video asset is never run through those filters (section 12: "do
# not apply image zoom filters to arbitrary videos unless supported
# safely") -- only trim/scale/crop, i.e. exactly the same cover-crop
# non-distorting strategy the STATIC branch of build_filter_graph already
# uses for images, reused here for video's own "no pan/zoom, just fill the
# frame" case.

SHORT_SOURCE_POLICIES = ("LOOP", "FREEZE", "REJECT")
DEFAULT_SHORT_SOURCE_POLICY = "FREEZE"


def _probe_video_duration(video_path: Path) -> float:
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise FileOperationError("ffprobe was not found on PATH -- is it installed/bundled?") from exc
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise FileOperationError(f"Invalid or unreadable video: {video_path}") from exc


def build_video_clip_command(
    video_path: Path, output_path: Path, duration: float, source_duration: float,
    fps: float, width: int, height: int, short_source_policy: str,
) -> list[str]:
    """Pure function: the complete, ready-to-run ffmpeg argv for turning an
    existing video asset into a Beat clip. No I/O, no subprocess.
    """
    is_short = source_duration < duration
    input_args = ["-stream_loop", "-1", "-i", str(video_path)] if (is_short and short_source_policy == "LOOP") else ["-i", str(video_path)]

    filter_stages = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        "setsar=1",
        "format=yuv420p",
        f"fps={fps}",
    ]
    if is_short and short_source_policy == "FREEZE":
        # Holds the last decoded frame for the remaining time instead of
        # ending early -- section 15's own explicit "do not silently choose
        # a surprising behavior": the clip is always exactly `duration`
        # long regardless of which policy is active.
        filter_stages.append(f"tpad=stop_mode=clone:stop_duration={max(0.0, duration - source_duration):.3f}")

    return _FFMPEG_PREFIX + input_args + [
        "-t", f"{duration}",
        "-vf", ",".join(filter_stages),
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-color_range", "tv",
        str(output_path),
    ]


def render_video_clip(
    video_path: Path | str,
    output_path: Path | str,
    duration: float,
    *,
    fps: float = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    short_source_policy: str = DEFAULT_SHORT_SOURCE_POLICY,
    on_process_start: Callable[[subprocess.Popen], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Turns an existing video asset into a Beat clip: trim to `duration`
    (section 14: Beat.duration is the source of truth, never an arbitrary
    fallback) + cover-scale/crop to the target frame -- never zoompan/
    rotate (section 12). If the source is shorter than `duration`,
    `short_source_policy` (LOOP/FREEZE/REJECT, section 15) decides what
    happens; there is no silent default beyond the one this function's own
    caller explicitly configured (see app.modules.beat.schemas.
    MotionProjectConfig.short_video_policy).
    """
    video_path = Path(video_path)
    output_path = Path(output_path)

    if short_source_policy not in SHORT_SOURCE_POLICIES:
        raise ValidationError(f"Unknown short_source_policy {short_source_policy!r}; must be one of {SHORT_SOURCE_POLICIES}")
    if not (MIN_DURATION <= duration <= MAX_DURATION):
        raise ValidationError(f"duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {duration}")
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise ValidationError(f"width/height must both be positive and even, got {width}x{height}")
    if not video_path.exists() or not video_path.is_file():
        raise FileOperationError(f"Input video not found: {video_path}")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise FileOperationError("ffmpeg/ffprobe was not found on PATH -- is it installed/bundled?")

    source_duration = _probe_video_duration(video_path)
    if source_duration <= 0:
        raise FileOperationError(f"Invalid or unreadable video (zero duration): {video_path}")
    if source_duration < duration and short_source_policy == "REJECT":
        raise ValidationError(
            f"Video asset {video_path} is {source_duration:.2f}s, shorter than the required {duration:.2f}s "
            "Beat duration, and short_source_policy is REJECT."
        )

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise FileOperationError(f"Cannot create output directory {output_path.parent}: {exc}") from exc

    command = build_video_clip_command(video_path, output_path, duration, source_duration, fps, width, height, short_source_policy)
    logger.info("Rendering video Beat clip: %s -> %s (duration=%.2fs, policy=%s)", video_path, output_path, duration, short_source_policy)

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise FileOperationError("ffmpeg was not found on PATH -- is it installed/bundled?") from exc

    if on_process_start is not None:
        on_process_start(process)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        if is_cancelled is not None and is_cancelled():
            raise RenderCancelled(f"Video Beat clip render for {video_path} was cancelled")
        logger.error("ffmpeg failed rendering video clip %s: %s", video_path, stderr[-2000:])
        raise FileOperationError(f"ffmpeg failed to render video Beat clip: {stderr.strip()[-2000:]}")

    if not output_path.exists():
        raise FileOperationError(f"ffmpeg reported success but produced no output file: {output_path}")

    return output_path


# -- Output validation (Task 23 section 39/40) ------------------------------


@dataclass
class ClipProbe:
    duration_sec: float
    width: int
    height: int
    fps: float
    codec: str


def probe_clip(path: Path | str) -> ClipProbe:
    """Full ffprobe-based validation of a rendered Beat clip -- never trust
    ffmpeg's own exit code alone (section 39). Raises FileOperationError if
    the file isn't a readable video at all.
    """
    path = Path(path)
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0 or not result.stdout.strip():
        raise FileOperationError(f"Not a readable video file: {path}")

    values: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values.setdefault(key.strip(), value.strip())

    try:
        duration = float(values["duration"])
        width = int(values["width"])
        height = int(values["height"])
        codec = values["codec_name"]
        num, _, den = values["r_frame_rate"].partition("/")
        fps = float(num) / float(den) if den and float(den) != 0 else float(num)
    except (KeyError, ValueError, ZeroDivisionError) as exc:
        raise FileOperationError(f"Could not parse video format for {path}: {exc}") from exc

    return ClipProbe(duration_sec=duration, width=width, height=height, fps=fps, codec=codec)


# A tiny, frame-based allowance (section 40: "do not require exact
# floating-point equality... use frame-based tolerance") -- container/
# encoder rounding can shift the reported duration by a fraction of a
# frame; this is not a real allowance for a genuinely wrong-length render.
_DURATION_TOLERANCE_FRAMES = 2
_FPS_TOLERANCE = 0.5


def validate_clip_output(probe: ClipProbe, expected_duration: float, expected_width: int, expected_height: int, expected_fps: float) -> None:
    """Section 39: duration/resolution/fps/codec, all checked -- raises
    FileOperationError with a clear message on the first mismatch found.
    """
    tolerance = _DURATION_TOLERANCE_FRAMES / expected_fps if expected_fps > 0 else 0.1
    if probe.duration_sec <= 0:
        raise FileOperationError(f"Rendered clip has zero/invalid duration: {probe.duration_sec}")
    if abs(probe.duration_sec - expected_duration) > tolerance:
        raise FileOperationError(
            f"Rendered clip duration {probe.duration_sec:.3f}s does not match the requested "
            f"{expected_duration:.3f}s (tolerance {tolerance:.3f}s)."
        )
    if probe.width != expected_width or probe.height != expected_height:
        raise FileOperationError(
            f"Rendered clip resolution {probe.width}x{probe.height} does not match the requested "
            f"{expected_width}x{expected_height}."
        )
    if abs(probe.fps - expected_fps) > _FPS_TOLERANCE:
        raise FileOperationError(f"Rendered clip fps {probe.fps:.2f} does not match the requested {expected_fps:.2f}.")
    if probe.codec not in ("h264",):
        raise FileOperationError(f"Rendered clip uses an unexpected codec {probe.codec!r} (expected h264).")
