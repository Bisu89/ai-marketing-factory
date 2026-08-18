"""The adapter boundary between the Video Factory contracts
(app.modules.composition / app.modules.motion) and the existing
app.modules.video_composer renderer -- see
docs/features/24-composition-video-composer-integration.md.

Per app/modules/README.md, no module may import another module.
`app.modules.video_composer` must not import `app.modules.motion`,
`app.modules.asset`, or `app.modules.beat`; `app.modules.composition` must
not import `app.modules.motion` or `app.modules.video_composer` either.
Something has to translate a CompositionPlan's Scenes into calls against
both the motion renderer and video_composer's job API, and per this
codebase's established "composition root" convention (the only place
`app/main.py` and `app/api/v1/router.py` are allowed to know about
multiple modules at once -- see app/modules/README.md), that translation
lives here: `app/api/v1/endpoints/*` is core HTTP-layer infrastructure,
not a module under app/modules/, so it may import all three.

`render_composition()` is the actual adapter logic (video_composer stays
completely unaware this file exists); `create_video_compose_job_from_composition`
is a thin HTTP wrapper around it, matching this app's own convention that
endpoint handlers "parse request, call service, map response" with no
business logic of their own (see docs/architecture.md).
"""

import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core import render_errors
from app.core.config import Settings, get_settings
from app.core.exceptions import FileOperationError, NotFoundError, RenderCancelled, ValidationError
from app.core.render_policy import enforce_local_rendering_policy
from app.core.render_profile import RenderProfile, get_render_profile
from app.db.session import get_db
from app.api.v1.endpoints.motion_generate import motion_artifact_for_beat
from app.modules.composition.schemas import CompositionPlan, Scene, SceneMotion
from app.modules.motion.renderer import render_motion_clip, render_video_clip
from app.modules.motion.schemas import Easing as MotionEasing
from app.modules.motion.schemas import MotionPlan, MotionPresetName
from app.modules.motion.schemas import PositionRange as MotionPositionRange
from app.modules.motion.schemas import RotationRange as MotionRotationRange
from app.modules.motion.schemas import ScaleRange as MotionScaleRange
from app.modules.video_composer.models import VideoComposeJob
from app.modules.video_composer.schemas import VideoComposeJobOut, job_to_out
from app.modules.video_composer.service import FONT_PATH, FONT_PATH_BOLD, VideoComposerService

router = APIRouter()

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}

# video_composer's own Form default for transition_duration (see
# app/modules/video_composer/router.py's create_video_compose_job) --
# reused here as the fallback when a CompositionPlan has nothing usable to
# derive one from.
_DEFAULT_TRANSITION_DURATION = 0.5


def _is_image_path(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


def _scene_motion_to_motion_plan(scene_motion: SceneMotion, duration: float) -> MotionPlan:
    """Converts Composition's own, deliberately-duplicated SceneMotion shape
    (see app/modules/composition/schemas.py's module docstring for why it's
    a duplicate, not an import, of Motion's MotionPlan) into a real
    MotionPlan the renderer accepts. This conversion is exactly what an
    adapter is for -- neither module is allowed to do it itself.
    """
    try:
        preset = MotionPresetName(scene_motion.preset_name)
    except ValueError:
        # preset_name is a free-form, unvalidated label on the Composition
        # side (see 22-composition-contract.md) -- it may be absent or not
        # match any real Motion preset. The renderer never branches on
        # `.preset` (see 23-local-motion-renderer.md), so any valid member
        # works here; this only affects a log line, never the rendered
        # output, which is driven entirely by the numeric fields below.
        preset = MotionPresetName.ZOOM_AND_PAN

    return MotionPlan(
        preset=preset,
        duration=duration,
        scale=MotionScaleRange(start=scene_motion.scale.start, end=scene_motion.scale.end),
        position=MotionPositionRange(
            x_start=scene_motion.position.x_start,
            y_start=scene_motion.position.y_start,
            x_end=scene_motion.position.x_end,
            y_end=scene_motion.position.y_end,
        ),
        rotation=MotionRotationRange(start=scene_motion.rotation.start, end=scene_motion.rotation.end),
        easing=MotionEasing(scene_motion.easing.value),
    )


def _compute_scene_start_times(scenes: list[Scene], transition_duration: float) -> dict[str, float]:
    """Approximates each Scene's start offset within the final merged
    video, using the exact same cumulative-duration-minus-overlap formula
    `video_composer.service._merge_clips_with_transitions` itself uses
    (shortest-clip-clamped `safe_transition`, then running `cumulative`) --
    reproduced here, not imported, since it's a handful of arithmetic lines
    on primitive floats, not a reason to reach into a private method.
    Uses each Scene's requested `duration` rather than a post-render probed
    duration, since this only needs to be good enough to place an SFX cue
    at roughly the right moment, not frame-accurate.
    """
    if not scenes:
        return {}
    shortest = min(scene.duration for scene in scenes)
    safe_transition = min(transition_duration, shortest / 2)

    starts: dict[str, float] = {scenes[0].id: 0.0}
    cumulative = scenes[0].duration
    for scene in scenes[1:]:
        starts[scene.id] = max(0.0, cumulative - safe_transition)
        cumulative = cumulative + scene.duration - safe_transition
    return starts


def _build_sfx_cues(scenes: list[Scene], transition_duration: float) -> list[dict]:
    """Every Scene with a non-null `audio.sfx` becomes one SFX cue timed to
    that scene's approximate start offset -- see
    `VideoComposerService._mix_audio`'s `sfx_cues` parameter.
    """
    starts = _compute_scene_start_times(scenes, transition_duration)
    return [
        {"path": scene.audio.sfx, "start_sec": starts[scene.id], "volume": scene.audio.sfx_volume}
        for scene in scenes
        if scene.audio.sfx
    ]


def _derive_transition_duration(scenes: list[Scene]) -> float:
    """video_composer only supports one uniform transition duration for an
    entire job (see app/modules/video_composer/service.py's
    _merge_clips_with_transitions) -- extending it to honor each Scene's own
    SceneTransition.duration/.type individually would mean rewriting that
    method's loop, which is explicitly out of scope ("do NOT rewrite the
    existing composer"). Averaging the durations of scenes that actually
    participate in a transition (order > 1 -- the first scene has nothing
    to transition from) is a deliberate, documented simplification, not an
    oversight; SceneTransition.type is not honored at all yet (every merge
    still uses video_composer's fixed "slideleft" style regardless of what
    a Scene requests). See docs/features/24-composition-video-composer-integration.md.
    """
    real_transitions = [scene.transition.duration for scene in scenes if scene.order > 1]
    if not real_transitions:
        return _DEFAULT_TRANSITION_DURATION
    return sum(real_transitions) / len(real_transitions)


def _run_preflight(
    plan: CompositionPlan,
    asset_paths: dict[int, str],
    narration_asset_paths: dict[int, str] | None,
    output_dir: str | None,
    min_free_disk_mb: int = 500,
    audio_master_path: str | None = None,
    captions_ass_path: str | None = None,
    watermark_path: str | None = None,
) -> None:
    """Validates everything cheap to check before any expensive ffmpeg work
    starts (Task 10 -- see docs/features/37-e2e-pipeline-hardening.md),
    covering Beats/Assets/Audio/Captions/Runtime in that order. Supersedes
    the narrower `_preflight_validate` this replaces (asset existence only,
    see docs/features/35-multi-beat-composition.md).

    Raises on the *first* problem found, using whichever of this codebase's
    existing exception types (app.core.exceptions) already fits that
    category -- ValidationError for "this plan/config is wrong",
    FileOperationError for "a referenced file/binary/directory isn't
    actually there" -- exactly the distinction the pre-existing preflight
    test suite already asserts on (a caller needs to tell "fix your input"
    apart from "your filesystem/runtime is missing something", and this
    codebase's app/main.py already maps each type to a different HTTP
    status for that reason). Each message is prefixed with a stable
    render_errors code so a caller (or a test) can match on the failure
    category without string-parsing the human-readable part.

    Beat-level structural checks (non-empty, contiguous 1-based order, valid
    duration bounds, a real source_asset_id) are already enforced by
    CompositionPlan/Scene's own Pydantic validators (see
    app/modules/composition/schemas.py) before this function is ever
    reached -- FastAPI rejects a structurally invalid plan with a 422 before
    the request body even finishes parsing. What's left to check here is
    everything Pydantic can't know: whether referenced *files* actually
    exist, and whether the runtime (ffmpeg/ffprobe, a writable output
    directory) is even available to render into.
    """
    scenes = plan.ordered_scenes()

    if not scenes:
        raise ValidationError(f"{render_errors.INVALID_BEAT_PLAN}: CompositionPlan has no scenes to render.")

    for scene in scenes:
        raw_path = asset_paths.get(scene.source_asset_id)
        if raw_path is None:
            raise ValidationError(
                f"{render_errors.MISSING_ASSET}: Beat {scene.order} (scene {scene.id!r}) has no visual asset "
                f"assigned (asset_id={scene.source_asset_id})."
            )
        if not Path(raw_path).exists():
            raise FileOperationError(
                f"{render_errors.MISSING_ASSET}: Beat {scene.order} (scene {scene.id!r}) references a missing "
                f"asset file: {raw_path}"
            )
        if not os.access(raw_path, os.R_OK):
            raise FileOperationError(
                f"{render_errors.MISSING_ASSET}: Beat {scene.order} (scene {scene.id!r}) asset file is not "
                f"readable: {raw_path}"
            )

    narration_asset_paths = narration_asset_paths or {}
    for scene in scenes:
        asset_id = scene.audio.narration_asset_id
        if asset_id is None:
            continue
        raw_path = narration_asset_paths.get(asset_id)
        if raw_path is None:
            raise ValidationError(
                f"{render_errors.MISSING_AUDIO}: Beat {scene.order} has a narration asset assigned "
                f"(asset_id={asset_id}) but no path was provided for it."
            )
        if not Path(raw_path).exists():
            raise FileOperationError(
                f"{render_errors.MISSING_AUDIO}: Beat {scene.order} references a missing narration audio "
                f"file: {raw_path}"
            )

    if plan.music_path and not Path(plan.music_path).exists():
        raise FileOperationError(f"{render_errors.MISSING_AUDIO}: Background music file not found: {plan.music_path}")

    # Task 26 (see docs/features/52-final-composer.md section 6) -- Final
    # Composer's own three project-level artifacts, when this render is
    # driven by factory_pipeline.py's own _stage_render (audio_master_path
    # set). All three come from validated artifact metadata resolved by
    # that composition root, never a raw frontend-supplied path (section 19).
    if audio_master_path is not None and not Path(audio_master_path).exists():
        raise FileOperationError(f"{render_errors.AUDIO_MASTER_MISSING}: Audio Master file not found: {audio_master_path}")
    if captions_ass_path is not None and not Path(captions_ass_path).exists():
        raise FileOperationError(f"{render_errors.CAPTION_ARTIFACT_MISSING}: Captions file not found: {captions_ass_path}")
    if watermark_path is not None and not Path(watermark_path).exists():
        raise FileOperationError(f"{render_errors.WATERMARK_ARTIFACT_MISSING}: Watermark file not found: {watermark_path}")

    for font_path in (FONT_PATH, FONT_PATH_BOLD):
        if not Path(font_path).exists():
            raise FileOperationError(
                f"{render_errors.INVALID_CAPTION_CONFIG}: Required caption font not found: {font_path}"
            )

    if shutil.which("ffmpeg") is None:
        raise FileOperationError(f"{render_errors.FFMPEG_NOT_FOUND}: ffmpeg was not found on PATH.")
    if shutil.which("ffprobe") is None:
        raise FileOperationError(f"{render_errors.FFPROBE_NOT_FOUND}: ffprobe was not found on PATH.")

    target_dir = Path(output_dir) if output_dir else Path.cwd()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        probe_file = target_dir / ".preflight_write_check"
        probe_file.write_text("", encoding="utf-8")
        probe_file.unlink()
    except OSError as exc:
        raise FileOperationError(
            f"{render_errors.OUTPUT_DIR_NOT_WRITABLE}: Output directory is not writable: {target_dir} ({exc})"
        ) from exc

    # Conservative fixed floor, not a real per-video size estimate (Task
    # 11 -- see docs/features/38-render-job-hardening.md): this pipeline's
    # own golden-sample/benchmark renders have produced sub-1MB outputs for
    # placeholder content and single-digit-MB for real photos, so 500MB
    # (Settings.min_free_disk_mb) comfortably covers normal use without
    # needing to model codec/bitrate/duration.
    try:
        free_mb = shutil.disk_usage(target_dir).free / (1024 * 1024)
    except OSError:
        free_mb = None
    if free_mb is not None and free_mb < min_free_disk_mb:
        raise FileOperationError(
            f"{render_errors.INSUFFICIENT_DISK_SPACE}: Only {free_mb:.0f}MB free at {target_dir}, "
            f"need at least {min_free_disk_mb}MB."
        )


# A tiny fraction of a second of slack for container/encoder rounding --
# not a real allowance for narration genuinely running long. Matches the
# same spirit as this codebase's other "exact-looking but not brittle"
# duration comparisons (see e.g. the golden sample render test's delta).
_NARRATION_DURATION_TOLERANCE_SEC = 0.15


def _probe_audio_duration(path: Path) -> float:
    """No shared ffmpeg/ffprobe wrapper exists anywhere in this codebase by
    design (see app/modules/motion/renderer.py's own module docstring) --
    this is this adapter's own small, local probe, not a reason to reach
    into VideoComposerService's private _probe_duration.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise FileOperationError(f"Could not read audio duration for {path}: not a valid audio file") from exc


def _resolve_narration(
    plan: CompositionPlan, narration_asset_paths: dict[int, str] | None, transition_duration: float
) -> tuple[str, list[dict] | None]:
    """Decides between this render's two narration modes and, for "local",
    builds+validates the per-beat spec list VideoComposerService needs.

    Backward compatible by construction: if no Scene has
    `audio.narration_asset_id` set, this returns ("tts", None) and nothing
    about the existing script_text/voice -> edge_tts path changes at all --
    every CompositionPlan built before this task (including every existing
    test fixture) has no such field set, so behaves exactly as before.

    Each spec's `duration` is the scene's crossfade-*adjusted* share of the
    timeline (every scene after the first loses `safe_transition` seconds
    to the overlap with its predecessor -- the exact same clamped formula
    `VideoComposerService._merge_clips_with_transitions` itself uses), not
    the scene's raw `duration`. Building the narration timeline from raw
    durations would drift out of sync with the actual merged video by
    `safe_transition` seconds per transition already passed -- up to
    several seconds by the last beat of a many-beat video. Validation
    ("narration exceeds Beat duration") still compares against the scene's
    own, raw, user-facing duration -- the crossfade overlap is a rendering
    detail, not something a beat's assigned narration should be rejected
    over.
    """
    scenes = plan.ordered_scenes()
    if not any(scene.audio.narration_asset_id for scene in scenes):
        return "tts", None

    # Same clamp _merge_clips_with_transitions applies (a transition can
    # never overlap more than half of the shorter of the two clips it sits
    # between) -- reproduced here, not imported, per this file's own
    # established "duplicate a few lines of arithmetic rather than reach
    # into a private method" convention (see _compute_scene_start_times).
    shortest = min(scene.duration for scene in scenes)
    safe_transition = min(transition_duration, shortest / 2)

    narration_asset_paths = narration_asset_paths or {}
    specs: list[dict] = []
    for index, scene in enumerate(scenes):
        timeline_duration = scene.duration if index == 0 else max(0.1, scene.duration - safe_transition)

        asset_id = scene.audio.narration_asset_id
        if asset_id is None:
            specs.append({"duration": timeline_duration, "path": None})
            continue

        raw_path = narration_asset_paths.get(asset_id)
        if raw_path is None:
            raise ValidationError(
                f"Beat {scene.order} has a narration asset assigned (asset_id={asset_id}) "
                "but no path was provided for it."
            )
        narration_path = Path(raw_path)
        if not narration_path.exists():
            raise FileOperationError(f"Beat {scene.order} references a missing narration audio file: {narration_path}")

        narration_duration = _probe_audio_duration(narration_path)
        if narration_duration > scene.duration + _NARRATION_DURATION_TOLERANCE_SEC:
            raise ValidationError(
                f"Beat {scene.order} narration is {narration_duration:.1f}s but Beat duration is "
                f"{scene.duration:.1f}s."
            )
        specs.append({"duration": timeline_duration, "path": str(narration_path)})

    return "local", specs


def render_beats_for_job(
    composition_request: dict,
    scenes_dir: Path,
    is_cancelled: Callable[[], bool],
    on_progress: Callable[[int, int], None],
    register_process: Callable[[subprocess.Popen | None], None],
) -> list[Path]:
    """RENDER_BEATS, run by VideoComposerService's own worker thread (Task
    11 moved this off the HTTP request thread that create_video_compose_job_from_composition
    runs on -- see docs/features/38-render-job-hardening.md). This is the
    concrete `VideoComposerService.BeatRenderer` implementation, injected
    at app/main.py (the composition root) exactly the way
    app.services.download.engine.DownloadEngine takes a pluggable
    `Downloader` -- video_composer/service.py never imports
    app.modules.motion or app.modules.composition itself; it only calls
    this function through that injected interface.

    `composition_request` is the same dict `render_composition` below
    persists onto the job (`{"plan": ..., "asset_paths": ..., ...}`, a
    plain JSON-round-tripped CompositionPlan -- dict keys are always
    strings after that round trip, unlike the original `dict[int, str]`
    asset_paths). Renders each image-backed Scene into a clip via
    app.modules.motion's renderer; a Scene whose asset is already a video
    clip is passed straight through, untouched -- unchanged from Task 10's
    version of this loop, just relocated and now cancellable/progress-
    reporting.
    """
    plan = CompositionPlan.model_validate(composition_request["plan"])
    asset_paths: dict[str, str] = composition_request["asset_paths"]
    # Task 23 (see docs/features/49-local-motion-engine.md) -- only present
    # when this job was created by factory_pipeline.py's own _stage_render
    # (a Factory project, which may have already run the GENERATING_MOTION
    # stage ahead of this render); the plain, non-Factory
    # create_video_compose_job_from_composition endpoint below never sets
    # these, so this whole cache-reuse path is a no-op for that flow --
    # exactly the same render it always was.
    project_id = composition_request.get("project_id")
    library_dir = composition_request.get("library_dir")
    scenes = plan.ordered_scenes()
    total = len(scenes)

    clip_paths: list[Path] = []
    for index, scene in enumerate(scenes):
        if is_cancelled():
            raise RenderCancelled()

        # asset_paths[...] and its existence were both already confirmed by
        # _run_preflight before this job was even created.
        source_path = Path(asset_paths[str(scene.source_asset_id)])
        output_clip = scenes_dir / f"{scene.id}.mp4"

        cached_clip = None
        if project_id is not None and library_dir is not None:
            cached_clip = motion_artifact_for_beat(
                project_id, scene.id, library_dir,
                scene.duration, scene.output_format.width, scene.output_format.height, scene.output_format.fps,
            )
        if cached_clip is not None:
            # Section 46's own cache win: an already-valid, already-
            # rendered artifact from a prior GENERATING_MOTION stage run,
            # reused outright rather than re-rendered from scratch.
            shutil.copyfile(cached_clip, output_clip)
            clip_paths.append(output_clip)
            on_progress(index + 1, total)
            continue

        if _is_image_path(source_path):
            motion_plan = _scene_motion_to_motion_plan(scene.motion, scene.duration)
            try:
                render_motion_clip(
                    source_path,
                    motion_plan,
                    output_clip,
                    duration=scene.duration,
                    fps=scene.output_format.fps,
                    width=scene.output_format.width,
                    height=scene.output_format.height,
                    on_process_start=register_process,
                    is_cancelled=is_cancelled,
                )
            finally:
                register_process(None)
        else:
            # Task 23 section 12/15: trim/scale/crop an existing video Beat
            # asset to the Beat's own duration/frame instead of passing it
            # through completely untouched (the previous behavior, which
            # never corrected a mismatched length or aspect ratio at all).
            try:
                render_video_clip(
                    source_path,
                    output_clip,
                    duration=scene.duration,
                    fps=scene.output_format.fps,
                    width=scene.output_format.width,
                    height=scene.output_format.height,
                    on_process_start=register_process,
                    is_cancelled=is_cancelled,
                )
            finally:
                register_process(None)
        clip_paths.append(output_clip)
        on_progress(index + 1, total)

    return clip_paths


def render_composition(
    plan: CompositionPlan,
    asset_paths: dict[int, str],
    service: VideoComposerService,
    title: str = "Composition",
    output_dir: str | None = None,
    narration_asset_paths: dict[int, str] | None = None,
    profile: str = "SOCIAL_VERTICAL",
    min_free_disk_mb: int = 500,
    project_id: int | None = None,
    library_dir: str | None = None,
    audio_master_path: str | None = None,
    captions_ass_path: str | None = None,
    watermark_path: str | None = None,
    watermark_position: str = "bottom-right",
    watermark_opacity: float = 1.0,
    watermark_scale: float = 0.15,
    watermark_margin_x: int = 24,
    watermark_margin_y: int = 24,
) -> int:
    """Turns a CompositionPlan into a persistent, queued VideoComposeJob --
    this app's `render_project`-equivalent single entry point (nothing else
    calls app.modules.motion or app.modules.video_composer to produce a
    Video Factory render). Only PREFLIGHT runs synchronously inside this
    function (and therefore inside the HTTP request that calls it,
    create_video_compose_job_from_composition below) -- it's fast (a
    handful of stat/PATH/disk-space checks, see _run_preflight) and
    rejecting a bad request immediately, before it's ever queued, is
    better UX than accepting a doomed job. RENDER_BEATS through
    VALIDATE_OUTPUT all now run on VideoComposerService's own worker
    thread (Task 11 -- see docs/features/38-render-job-hardening.md;
    render_beats_for_job above is what the worker actually calls),
    exactly like the plain upload-based Video Composer flow already did --
    this function returns as soon as the job is queued, without waiting
    for any rendering at all.

    `asset_paths` maps each Scene.source_asset_id to a real filesystem path.
    Resolving that mapping (e.g. by querying app.modules.asset) is
    deliberately the caller's responsibility, not this function's -- it
    keeps this adapter's own dependency surface to exactly the three
    modules this integration is about (composition, motion, video_composer),
    matching this task's "smallest safe change" instruction rather than
    also wiring in Asset lookups that weren't asked for.

    `project_id`/`library_dir` (Task 23, both optional, default None) --
    when given (factory_pipeline.py's own _stage_render always supplies
    them; the plain create_video_compose_job_from_composition endpoint
    below never does), render_beats_for_job checks for a cached, still-
    valid GENERATING_MOTION-stage artifact for each beat before rendering
    it fresh. None for either is a complete no-op for this cache-reuse path
    -- the plain, non-Factory render flow is unchanged.

    `audio_master_path` (Task 26 -- see docs/features/52-final-composer.md,
    both optional, default None): when set (factory_pipeline.py's own
    _stage_render always supplies it, a real, already-validated
    audio_master.wav; the plain create_video_compose_job_from_composition
    endpoint below never does), this render skips TTS/local-narration
    generation and _mix_audio entirely -- the given file becomes the sole
    final audio track, and `_resolve_narration` below is never even called.
    `captions_ass_path`/`watermark_*` are only meaningful together with it.
    """
    enforce_local_rendering_policy()
    # Validates `profile` is a real, known name (raises ValidationError
    # otherwise) and is recorded on the job (render_profile column) for
    # reporting/final-validation bookkeeping. Deliberately does NOT
    # override each Scene's own output_format: that field is Composition's
    # authoritative per-scene contract (see app/modules/composition/schemas.py),
    # and some real callers (including this codebase's own test suite)
    # legitimately vary it per scene -- e.g. small dimensions for fast
    # test renders. A caller that wants every scene to actually render at
    # a given profile's resolution sets that profile's width/height/fps on
    # every Scene.output_format itself (the frontend does this already --
    # see frontend/src/pages/VideoFactoryPage.tsx's OUTPUT_FORMAT
    # constant, which mirrors app.core.render_profile.SOCIAL_VERTICAL).
    render_profile = get_render_profile(profile)

    preflight_start = time.monotonic()
    _run_preflight(
        plan, asset_paths, narration_asset_paths, output_dir, min_free_disk_mb,
        audio_master_path=audio_master_path, captions_ass_path=captions_ass_path, watermark_path=watermark_path,
    )
    preflight_seconds = time.monotonic() - preflight_start

    transition_duration = _derive_transition_duration(plan.scenes)
    sfx_cues = _build_sfx_cues(plan.scenes, transition_duration)
    if audio_master_path is not None:
        # Task 26 -- Final Composer supplies its own complete audio; no
        # per-beat narration timeline to build, no TTS to run.
        narration_mode, beat_narration_specs = "precomposed", None
    else:
        narration_mode, beat_narration_specs = _resolve_narration(plan, narration_asset_paths, transition_duration)

    # Persisted so the worker can render beats itself (render_beats_for_job
    # above) and so a later retry_job() can rebuild an equivalent request.
    # JSON round-trips dict keys to strings -- render_beats_for_job already
    # accounts for that. mode="json" makes every value (enums, etc.) plain
    # JSON-serializable up front, rather than relying on the JSON column's
    # own encoder to know how.
    composition_request_json = {
        "plan": plan.model_dump(mode="json"),
        "asset_paths": {str(k): v for k, v in asset_paths.items()},
        "narration_asset_paths": {str(k): v for k, v in (narration_asset_paths or {}).items()},
        "profile": profile,
        "project_id": project_id,
        "library_dir": library_dir,
    }

    # Section 14/17: captions are burned in only when a real ASS artifact is
    # actually available -- for narration_mode="precomposed" that means
    # `captions_ass_path` was actually given (Task 25's Caption Engine ran
    # and produced a valid captions.ass); for "local" there's no word-
    # boundary data to caption from at all (docs/features/36-audio-pipeline.md).
    if narration_mode == "precomposed":
        burn_subtitles = captions_ass_path is not None
    else:
        burn_subtitles = narration_mode != "local"

    job_id = service.create_job(
        title=title,
        script_text=plan.narration_script or "",
        voice=plan.voice,
        music_volume=plan.music_volume,
        transition_duration=transition_duration,
        burn_subtitles=burn_subtitles,
        requested_output_dir=output_dir,
        narration_volume=plan.narration_volume,
        music_ducking_ratio=plan.music_ducking_ratio,
        fade_in_sec=plan.fade_in_sec,
        fade_out_sec=plan.fade_out_sec,
        caption_preset=plan.caption_preset.value,
        sfx_cues=sfx_cues or None,
        narration_mode=narration_mode,
        beat_narration_specs=beat_narration_specs,
        render_profile=render_profile.name,
        preflight_seconds=preflight_seconds,
        composition_request_json=composition_request_json,
        audio_master_path=audio_master_path,
        captions_ass_path=captions_ass_path,
        watermark_enabled=watermark_path is not None,
        watermark_path=watermark_path,
        watermark_position=watermark_position,
        watermark_opacity=watermark_opacity,
        watermark_scale=watermark_scale,
        watermark_margin_x=watermark_margin_x,
        watermark_margin_y=watermark_margin_y,
    )
    # Task 26: a precomposed job's audio comes entirely from audio_master_path
    # -- plan.music_path (the old per-job BGM field) is never separately
    # attached, since Audio Master already contains BGM if any was mixed in.
    if plan.music_path and narration_mode != "precomposed":
        service.set_music_path(job_id, plan.music_path)

    service.enqueue(job_id)
    return job_id


class CompositionRenderRequest(BaseModel):
    plan: CompositionPlan
    asset_paths: dict[int, str]
    title: str = "Composition"
    output_dir: str | None = None
    narration_asset_paths: dict[int, str] | None = None
    profile: str = "SOCIAL_VERTICAL"


def get_video_composer_service(request: Request) -> VideoComposerService:
    return request.app.state.video_composer_service


@router.post("/video-compose-jobs/from-composition", response_model=VideoComposeJobOut, status_code=201)
def create_video_compose_job_from_composition(
    payload: CompositionRenderRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
):
    job_id = render_composition(
        payload.plan,
        payload.asset_paths,
        service,
        payload.title,
        payload.output_dir,
        narration_asset_paths=payload.narration_asset_paths,
        profile=payload.profile,
        min_free_disk_mb=settings.min_free_disk_mb,
    )
    job = (
        db.query(VideoComposeJob)
        .options(selectinload(VideoComposeJob.clips))
        .filter(VideoComposeJob.id == job_id)
        .first()
    )
    if job is None:
        raise NotFoundError("Video compose job", job_id)
    return job_to_out(job, Path(settings.library_dir))
