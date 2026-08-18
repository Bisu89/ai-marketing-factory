"""The Audio Master rendering engine (Task 24 -- see
docs/features/50-audio-master.md): mixes narration + optional local BGM
into one lossless `audio_master.wav`, ducking BGM under narration via
ffmpeg's own `sidechaincompress` filter -- the exact same real, dynamic
ducking recipe app.modules.video_composer.service.VideoComposerService's
own `_mix_audio` already uses and has in production, duplicated here (not
imported -- module isolation, see app/modules/README.md) per this
codebase's own established "duplicate a proven filter graph across a
module boundary" convention (see app/modules/motion/renderer.py's own
module docstring for the identical reasoning applied to zoompan).

No shared ffmpeg wrapper exists anywhere in this codebase by design (same
precedent) -- this file runs its own `subprocess.run(["ffmpeg", ...])`
calls, safe argument arrays throughout, never a concatenated shell string.
"""

import logging
import shutil
import subprocess
from pathlib import Path

from app.modules.audio.schemas import (
    AUDIO_CLIPPING,
    AUDIO_DURATION_MISMATCH,
    AUDIO_MIX_FAILED,
    AUDIO_OUTPUT_INVALID,
    AUDIO_SILENT,
    AudioError,
    AudioMixPlan,
    AudioProbe,
)

logger = logging.getLogger(__name__)

# Section 21/22 -- a stable internal format for the lossless intermediate
# artifact; final video encoding (a later task) handles compression.
OUTPUT_SAMPLE_RATE = 48000
OUTPUT_CHANNELS = 2

# Section 19/20 -- a practical social-video loudness target. Chosen (not
# discovered from an existing project setting -- none exists yet) and
# applied via ffmpeg's own single-pass `loudnorm` filter; this is a
# reasonable target, not a claim of exact, measured broadcast-grade
# compliance (single-pass loudnorm is an approximation, not a two-pass
# analyze-then-correct pipeline).
LOUDNESS_TARGET_LUFS = -14.0
TRUE_PEAK_CEILING_DBTP = -1.0
LOUDNESS_RANGE_TARGET = 11.0

# Bumped whenever this mixing pipeline's actual output would differ from
# what an old cached artifact already contains (section 26/27) -- part of
# the audio_generate.py composition root's own cache fingerprint.
MIX_VERSION = "audio-mix-v1"

# Matches app.modules.voice.audio_analysis's own silence threshold
# (duplicated, not imported -- module isolation) -- real, audible mixed
# audio reads well above this; anything at or below is "essentially
# nothing was produced."
_SILENCE_MEAN_VOLUME_DB_THRESHOLD = -50.0
# ffmpeg's own dBFS scale tops out at 0 (full scale); loudnorm's TP ceiling
# above should keep real output well clear of this, so a max_volume this
# close to 0dBFS in the *final* mixed-and-normalized output is a real,
# unexpected clipping signal, not a normal loud passage.
_CLIPPING_MAX_VOLUME_DB_THRESHOLD = -0.1

_FFMPEG_PREFIX = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"]

# A tiny, frame/sample-scale allowance (section 31: "within a small
# frame/sample tolerance") -- container/encoder rounding, not a real
# allowance for a genuinely wrong-length mix.
_DURATION_TOLERANCE_SEC = 0.15


def build_ffmpeg_command(plan: AudioMixPlan, output_path: Path) -> list[str]:
    """Pure function: the complete, ready-to-run ffmpeg argv. No I/O, no
    subprocess -- safe and fast to unit test directly.

    Mirrors VideoComposerService._mix_audio's own filter graph shape
    (narration always present, optional BGM ducked via sidechaincompress,
    amix, apad/afade) with two differences: this is a standalone,
    project-level artifact (not muxed into a merged video), and the final
    stage always runs `loudnorm` to a fixed target (section 19/20) --
    _mix_audio's own render-time mix does not, since final loudness there
    is this task's own new concern, not an existing one to preserve.
    """
    inputs: list[str] = ["-i", plan.narration_path]
    filters: list[str] = [f"[0:a]volume={plan.narration_volume},apad=whole_dur={plan.target_duration}[narration]"]
    mix_labels = ["narration"]
    next_index = 1

    if plan.bgm_path:
        # -stream_loop -1: BGM shorter than narration loops seamlessly
        # (section 10) rather than needing a separate loop-detection/concat
        # step; a BGM longer than narration is simply trimmed by the
        # eventual `-t target_duration` on the whole command (section 11).
        inputs += ["-stream_loop", "-1", "-i", plan.bgm_path]
        filters.append(f"[{next_index}:a]volume={plan.bgm_volume}[bgm_pre]")
        if plan.ducking_enabled:
            # sidechaincompress: BGM (main input) is compressed using
            # narration (sidechain input) as the trigger -- BGM level
            # drops automatically whenever narration is actually speaking
            # (section 13/14), and returns to normal during silence.
            # threshold/attack/release are fixed, sensible defaults for
            # speech-over-music (matching _mix_audio's own proven values);
            # `ratio` is the one knob exposed as ducking_ratio (section 15).
            filters.append(
                f"[bgm_pre][narration]sidechaincompress=threshold=0.05:"
                f"ratio={plan.ducking_ratio}:attack=5:release=300[ducked]"
            )
            mix_labels.append("ducked")
        else:
            mix_labels.append("bgm_pre")
        next_index += 1

    if len(mix_labels) > 1:
        mix_inputs = "".join(f"[{label}]" for label in mix_labels)
        filters.append(f"{mix_inputs}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0[mixed]")
        last_label = "mixed"
    else:
        last_label = "narration"

    # Final apad=whole_dur, always applied -- sidechaincompress/amix can
    # truncate back to the shortest real input even when every upstream
    # branch was already padded (the same real bug _mix_audio's own
    # docstring documents finding); padding the fully-combined stream here,
    # right before the end, is a safe no-op once it's already long enough.
    # The outer -t below remains the final, authoritative trim (section 31:
    # narration duration is the source of truth).
    final_ops = [f"apad=whole_dur={plan.target_duration}"]
    if plan.fade_in_sec > 0:
        final_ops.append(f"afade=t=in:st=0:d={plan.fade_in_sec}")
    if plan.fade_out_sec > 0:
        fade_out_start = max(0.0, plan.target_duration - plan.fade_out_sec)
        final_ops.append(f"afade=t=out:st={fade_out_start}:d={plan.fade_out_sec}")
    # Section 19/20 -- single-pass loudness normalization to a fixed,
    # documented target; applied last so fades/ducking are already baked
    # into the signal loudnorm measures.
    final_ops.append(f"loudnorm=I={LOUDNESS_TARGET_LUFS}:TP={TRUE_PEAK_CEILING_DBTP}:LRA={LOUDNESS_RANGE_TARGET}")
    filters.append(f"[{last_label}]{','.join(final_ops)}[a]")

    return _FFMPEG_PREFIX + inputs + [
        "-filter_complex", ";".join(filters),
        "-map", "[a]",
        "-t", str(plan.target_duration),
        "-ar", str(OUTPUT_SAMPLE_RATE),
        "-ac", str(OUTPUT_CHANNELS),
        "-c:a", "pcm_s16le",
        str(output_path),
    ]


def render_audio_master(plan: AudioMixPlan, output_path: Path) -> Path:
    """Renders one AudioMixPlan into a real WAV file at `output_path`.
    Raises AudioError(AUDIO_MIX_FAILED) on any ffmpeg failure -- never
    returns a partial/placeholder result.
    """
    output_path = Path(output_path)

    if not Path(plan.narration_path).exists():
        raise AudioError(AUDIO_MIX_FAILED, f"Narration file not found: {plan.narration_path}")
    if plan.bgm_path and not Path(plan.bgm_path).exists():
        raise AudioError(AUDIO_MIX_FAILED, f"BGM file not found: {plan.bgm_path}")
    if shutil.which("ffmpeg") is None:
        raise AudioError(AUDIO_MIX_FAILED, "ffmpeg was not found on PATH -- is it installed/bundled?")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AudioError(AUDIO_MIX_FAILED, f"Cannot create output directory {output_path.parent}: {exc}") from exc

    command = build_ffmpeg_command(plan, output_path)
    logger.info(
        "Rendering audio master: narration=%s bgm=%s -> %s (duration=%.2fs, ducking=%s)",
        plan.narration_path, plan.bgm_path, output_path, plan.target_duration, plan.ducking_enabled,
    )

    result = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        logger.error("ffmpeg failed mixing audio master: %s", result.stderr[-2000:])
        raise AudioError(AUDIO_MIX_FAILED, f"ffmpeg failed to mix audio master: {result.stderr.strip()[-2000:]}")
    if not output_path.exists():
        raise AudioError(AUDIO_MIX_FAILED, f"ffmpeg reported success but produced no output file: {output_path}")

    return output_path


# -- Output analysis/validation (section 25/30/44/45/46) --------------------


def probe_audio(path: Path) -> AudioProbe:
    """Section 44's minimum analysis -- duration/format from ffprobe, mean/
    max volume (silence + clipping detection) from ffmpeg's own
    `volumedetect` filter. Mirrors app.modules.voice.audio_analysis's own
    probe_audio exactly (duplicated, not imported -- module isolation).
    """
    path = Path(path)
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,sample_rate,channels",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1",
            str(path),
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    if probe.returncode != 0 or not probe.stdout.strip():
        raise AudioError(AUDIO_OUTPUT_INVALID, f"Not a readable audio file: {path}")

    values: dict[str, str] = {}
    for line in probe.stdout.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values.setdefault(key.strip(), value.strip())

    try:
        duration = float(values["duration"])
        sample_rate = int(values["sample_rate"])
        channels = int(values["channels"])
        codec = values["codec_name"]
    except (KeyError, ValueError) as exc:
        raise AudioError(AUDIO_OUTPUT_INVALID, f"Could not parse audio format for {path}: {exc}") from exc

    mean_volume_db, max_volume_db = _probe_loudness(path)
    return AudioProbe(
        duration_sec=duration, sample_rate=sample_rate, channels=channels, codec=codec,
        mean_volume_db=mean_volume_db, max_volume_db=max_volume_db,
    )


def _probe_loudness(path: Path) -> tuple[float | None, float | None]:
    result = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    mean_db = max_db = None
    for line in result.stderr.splitlines():
        line = line.strip()
        if "mean_volume:" in line:
            mean_db = _parse_db(line)
        elif "max_volume:" in line:
            max_db = _parse_db(line)
    return mean_db, max_db


def _parse_db(line: str) -> float | None:
    try:
        return float(line.split(":", 1)[1].strip().rstrip("dB").strip())
    except (IndexError, ValueError):
        return None


def validate_audio_master(probe: AudioProbe, expected_duration: float) -> None:
    """Section 30/44/45/46: raises with a stable code the very first time
    any rule is violated -- never marks Audio COMPLETED on a technicality.
    Called *before* the caller persists/checkpoints anything (Task 19's
    own "validate, then persist, then checkpoint" ordering, reused here).
    """
    if probe.duration_sec <= 0:
        raise AudioError(AUDIO_OUTPUT_INVALID, "Audio master has zero/invalid duration.")
    if abs(probe.duration_sec - expected_duration) > _DURATION_TOLERANCE_SEC:
        raise AudioError(
            AUDIO_DURATION_MISMATCH,
            f"Audio master duration {probe.duration_sec:.2f}s does not match narration duration "
            f"{expected_duration:.2f}s.",
        )
    if probe.mean_volume_db is not None and probe.mean_volume_db <= _SILENCE_MEAN_VOLUME_DB_THRESHOLD:
        raise AudioError(
            AUDIO_SILENT, f"Audio master is essentially silent (mean volume {probe.mean_volume_db:.1f}dB)."
        )
    if probe.max_volume_db is not None and probe.max_volume_db > _CLIPPING_MAX_VOLUME_DB_THRESHOLD:
        raise AudioError(
            AUDIO_CLIPPING, f"Audio master peak {probe.max_volume_db:.1f}dB exceeds the safe ceiling."
        )
