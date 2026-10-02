"""Voice test bench: paste a story, pick a voice + speed, get an MP3 back.

Standalone from the Voice Factory stage (voice_generate.py) -- no project,
no beats, no Asset registration. It only reuses EdgeTTSProvider (sentence
splitting, pauses, retries, the process-wide edge_tts semaphore) so a long
story goes through the same hardened path as a real render, then encodes the
result to MP3 with the bundled ffmpeg.

Synthesis of a ~2000-word story takes minutes, so POST starts a background
thread and returns a job id; the page polls GET /jobs/{id}.
"""

import logging
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.voice.providers import EdgeTTSProvider

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TEXT_CHARS = 60_000
DEFAULT_VOICE = "vi-VN-HoaiMyNeural"

# Small curated edge_tts set (same free service the rest of the app uses).
VOICES = [
    {"id": "vi-VN-HoaiMyNeural", "label": "Tiếng Việt — Hoài My (nữ)", "language": "vi"},
    {"id": "vi-VN-NamMinhNeural", "label": "Tiếng Việt — Nam Minh (nam)", "language": "vi"},
    {"id": "ko-KR-SunHiNeural", "label": "Tiếng Hàn — Sun-Hi (nữ)", "language": "ko"},
    {"id": "ko-KR-InJoonNeural", "label": "Tiếng Hàn — In-Joon (nam)", "language": "ko"},
    {"id": "en-US-JennyNeural", "label": "English (US) — Jenny (nữ)", "language": "en"},
    {"id": "en-US-AriaNeural", "label": "English (US) — Aria (nữ)", "language": "en"},
    {"id": "en-US-GuyNeural", "label": "English (US) — Guy (nam)", "language": "en"},
    {"id": "en-GB-SoniaNeural", "label": "English (UK) — Sonia (nữ)", "language": "en"},
]
_VOICE_LANGUAGE = {v["id"]: v["language"] for v in VOICES}

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


class VoiceTestIn(BaseModel):
    text: str
    voice: str = DEFAULT_VOICE
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


def clean_story_text(raw: str) -> str:
    """Drops script notes (lines starting with '##') and collapses blank
    lines, so a story file can be pasted as-is."""
    lines = [ln.strip() for ln in raw.splitlines() if not ln.strip().startswith("##")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _output_dir(settings: Settings) -> Path:
    path = Path(settings.library_dir) / "_voice_test"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_job(job_id: str, text: str, voice: str, speed: float, out_dir: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = out_dir / f".{job_id}.wav"
    mp3_path = out_dir / f"giong-doc_{stamp}_{job_id[:6]}.mp3"
    started = time.time()
    try:
        result = EdgeTTSProvider().synthesize(text, voice, _VOICE_LANGUAGE.get(voice, "vi"), speed, wav_path)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0 or not mp3_path.exists():
            raise RuntimeError(f"Không xuất được MP3: {proc.stderr.strip()}")
        update = {
            "status": "done", "file": str(mp3_path), "filename": mp3_path.name,
            "duration_sec": round(result.duration_sec, 1), "elapsed_sec": round(time.time() - started, 1),
        }
    except Exception as exc:  # noqa: BLE001 -- surfaced to the page as the job's error text
        logger.exception("voice test job %s failed", job_id)
        update = {"status": "error", "error": str(exc)}
    finally:
        wav_path.unlink(missing_ok=True)
    with _jobs_lock:
        _jobs[job_id].update(update)


@router.get("/voice-test/voices")
def list_test_voices() -> dict:
    return {"default": DEFAULT_VOICE, "voices": VOICES}


@router.post("/voice-test/synthesize")
def start_voice_test(payload: VoiceTestIn, settings: Settings = Depends(get_settings)) -> dict:
    text = clean_story_text(payload.text)
    if not text:
        raise ValidationError("Chưa có nội dung để đọc.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValidationError(f"Truyện quá dài ({len(text)} ký tự, tối đa {MAX_TEXT_CHARS}). Hãy chia nhỏ ra.")
    if payload.voice not in _VOICE_LANGUAGE:
        raise ValidationError(f"Giọng đọc không hỗ trợ: {payload.voice}")

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "chars": len(text), "words": len(text.split())}
    threading.Thread(
        target=_run_job, args=(job_id, text, payload.voice, payload.speed, _output_dir(settings)), daemon=True,
    ).start()
    return {"job_id": job_id, "chars": len(text), "words": len(text.split())}


def _get_job(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"Không tìm thấy job {job_id}.")
        return dict(job)


@router.get("/voice-test/jobs/{job_id}")
def get_voice_test_job(job_id: str) -> dict:
    job = _get_job(job_id)
    job.pop("file", None)
    return job


@router.get("/voice-test/jobs/{job_id}/audio")
def get_voice_test_audio(job_id: str, download: bool = False) -> FileResponse:
    job = _get_job(job_id)
    if job.get("status") != "done" or not Path(job["file"]).exists():
        raise NotFoundError("File MP3 chưa sẵn sàng.")
    return FileResponse(
        job["file"], media_type="audio/mpeg", filename=job["filename"],
        content_disposition_type="attachment" if download else "inline",
    )
