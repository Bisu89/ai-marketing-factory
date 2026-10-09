"""ffmpeg / ffprobe helpers for the documentary module. Arguments are always
passed as a list (never through a shell, never built from user text), with a
timeout. ffprobe *measures* a file; it does not align speech to text."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.exceptions import ValidationError

SAMPLE_RATE = 48000
_TIMEOUT_SEC = 600


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=_TIMEOUT_SEC)
    except FileNotFoundError as exc:
        raise ValidationError(f"Không tìm thấy {cmd[0]} — cần ffmpeg/ffprobe trong PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValidationError(f"{cmd[0]} chạy quá thời gian cho phép.") from exc


def probe_duration(path: Path) -> float:
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    try:
        d = float(r.stdout.strip())
    except ValueError:
        raise ValidationError(f"Không đọc được thời lượng audio: {path.name}") from None
    if d <= 0:
        raise ValidationError(f"Audio có thời lượng không hợp lệ ({d}s): {path.name}")
    return d


def has_audio_stream(path: Path) -> bool:
    r = _run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)])
    return r.returncode == 0 and "audio" in r.stdout


def _check(r: subprocess.CompletedProcess, what: str) -> None:
    if r.returncode != 0:
        raise ValidationError(f"{what} thất bại: {r.stderr.strip()[-500:]}")


def make_silence(dest: Path, seconds: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _check(
        _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono",
              "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", str(dest)]),
        "Tạo đoạn im lặng",
    )


def to_wav(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _check(
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ar", str(SAMPLE_RATE), "-ac", "1",
              "-c:a", "pcm_s16le", str(dest)]),
        "Chuyển audio sang WAV",
    )


def concat_wavs(parts: list[Path], dest: Path) -> None:
    """Lossless concat of same-format WAVs (all produced by to_wav / make_silence)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    listing = dest.with_suffix(".txt")
    # concat demuxer syntax: single quotes inside paths are escaped as '\''
    listing.write_text(
        "".join("file '" + p.resolve().as_posix().replace("'", "'\\''") + "'\n" for p in parts), encoding="utf-8"
    )
    try:
        _check(
            _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dest)]),
            "Ghép narration master",
        )
    finally:
        listing.unlink(missing_ok=True)
