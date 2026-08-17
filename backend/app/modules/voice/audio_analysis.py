"""Audio analysis + normalization (Task 22 sections 10-13, 34-36). Reuses
this app's already-bundled ffmpeg/ffprobe (see resources/ffmpeg, prepended
to PATH by app.core.config for a packaged build) -- no new DSP framework,
no shared ffmpeg wrapper (matching composition_render.py's own
"no shared ffmpeg/ffprobe wrapper by design" convention, see that file's
_probe_audio_duration docstring).
"""

import subprocess
from pathlib import Path

from app.modules.voice.schemas import (
    TTS_INVALID_OUTPUT,
    VOICE_FORMAT_INVALID,
    VOICE_SILENT,
    AudioProbe,
    VoiceError,
)

# Section 11's own recommendation -- the one internal format every VOICE
# artifact is normalized to, regardless of which provider produced it, so
# nothing downstream ever has to branch on "which engine made this file."
CANONICAL_SAMPLE_RATE = 48000
CANONICAL_CHANNELS = 1

# Section 36: audio quieter than this (ffmpeg's own dBFS scale, 0 = full
# scale, more negative = quieter) is "near-total silence" -- a real,
# audible SAPI5/edge_tts narration typically reads well above -35dB mean;
# -50dB is deep into "essentially nothing was spoken."
_SILENCE_MEAN_VOLUME_DB_THRESHOLD = -50.0


def normalize_audio(source: Path, destination: Path) -> None:
    """Resamples/remixes to the canonical WAV format (section 11/12) --
    the one place any provider's raw output gets converted, so a provider
    is free to emit whatever sample rate/channel count/container it wants
    natively. Writes to `destination` directly; the caller is responsible
    for atomic tmp-path handling (section 31), not this function.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(source),
            "-ar", str(CANONICAL_SAMPLE_RATE), "-ac", str(CANONICAL_CHANNELS),
            "-c:a", "pcm_s16le",
            str(destination),
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not destination.exists():
        raise VoiceError(VOICE_FORMAT_INVALID, f"Could not normalize audio to WAV: {result.stderr.strip()}")


def cut_segment(source: Path, destination: Path, start: float, end: float) -> None:
    """Trims one Beat's own window out of the project's canonical
    narration.wav -- the per-beat artifact that gets registered as a real
    local Asset and assigned to Beat.narration_asset_id (see
    voice_generate.py), reusing app.modules.video_composer's existing,
    already-tested narration_mode="local" render path unchanged.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.01, end - start)
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(source), "-ss", str(start), "-t", str(duration),
            "-ar", str(CANONICAL_SAMPLE_RATE), "-ac", str(CANONICAL_CHANNELS), "-c:a", "pcm_s16le",
            str(destination),
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not destination.exists():
        raise VoiceError(VOICE_FORMAT_INVALID, f"Could not cut beat audio segment: {result.stderr.strip()}")


def probe_audio(path: Path) -> AudioProbe:
    """Section 34's minimum analysis. Duration/format come from ffprobe;
    mean/max volume (used only for silence detection, section 36 -- not
    full LUFS metering, section 35's own explicit MVP scope-out) come from
    ffmpeg's `volumedetect` filter, the same filter this codebase's own
    existing tests already use for the identical purpose (see
    tests/modules/video_composer/test_audio_pipeline.py).
    """
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
        raise VoiceError(VOICE_FORMAT_INVALID, f"Not a readable audio file: {path}")

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
        raise VoiceError(VOICE_FORMAT_INVALID, f"Could not parse audio format for {path}: {exc}") from exc

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


def validate_audio(probe: AudioProbe) -> None:
    """Section 10/14/36: raises with a stable code the very first time any
    rule is violated -- never marks Voice COMPLETED on a technicality.
    Called *before* the caller persists/checkpoints anything (Task 19's
    own "validate, then persist, then checkpoint" ordering, reused here).
    """
    if probe.duration_sec <= 0:
        raise VoiceError(TTS_INVALID_OUTPUT, "Synthesized audio has zero duration.")
    if probe.sample_rate <= 0 or probe.channels <= 0:
        raise VoiceError(VOICE_FORMAT_INVALID, f"Invalid audio format: sample_rate={probe.sample_rate}, channels={probe.channels}")
    if probe.mean_volume_db is not None and probe.mean_volume_db <= _SILENCE_MEAN_VOLUME_DB_THRESHOLD:
        raise VoiceError(
            VOICE_SILENT,
            f"Synthesized audio is essentially silent (mean volume {probe.mean_volume_db:.1f}dB).",
        )
