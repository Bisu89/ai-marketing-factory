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
import os
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
from app.modules.voice.providers import EdgeTTSProvider, synthesize_voice_runs

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TEXT_CHARS = 60_000
DEFAULT_VOICE = "vi-VN-HoaiMyNeural"

# Small curated edge_tts set (same free service the rest of the app uses).
VOICES = [
    {"id": "vi-VN-HoaiMyNeural", "label": "Tiếng Việt — Hoài My (nữ)", "language": "vi", "gender": "f"},
    {"id": "vi-VN-NamMinhNeural", "label": "Tiếng Việt — Nam Minh (nam)", "language": "vi", "gender": "m"},
    {"id": "ko-KR-SunHiNeural", "label": "Tiếng Hàn — Sun-Hi (nữ)", "language": "ko", "gender": "f"},
    {"id": "ko-KR-InJoonNeural", "label": "Tiếng Hàn — In-Joon (nam)", "language": "ko", "gender": "m"},
    {"id": "en-US-JennyNeural", "label": "English (US) — Jenny (nữ)", "language": "en", "gender": "f"},
    {"id": "en-US-AriaNeural", "label": "English (US) — Aria (nữ)", "language": "en", "gender": "f"},
    {"id": "en-US-GuyNeural", "label": "English (US) — Guy (nam)", "language": "en", "gender": "m"},
    {"id": "en-GB-SoniaNeural", "label": "English (UK) — Sonia (nữ)", "language": "en", "gender": "f"},
]
_VOICE_LANGUAGE = {v["id"]: v["language"] for v in VOICES}
_VOICE_GENDER = {v["id"]: v["gender"] for v in VOICES}

# Section headers inside a pasted script (they are '##' lines, which are otherwise notes and
# dropped): the intro and outro of an episode are read by a second voice -- by series rule the
# opposite gender of the main narrator (KO: female narrator + male bookends; VI: the reverse).
_INTRO_RE = re.compile(r"^##\s*(GIỚI THIỆU|INTRO)\b", re.IGNORECASE)
_OUTRO_RE = re.compile(r"^##\s*(KẾT|OUTRO)\b", re.IGNORECASE)
_BODY_RE = re.compile(r"^##\s*(TRUYỆN|BODY|LỜI ĐỌC|NỘI DUNG)\b", re.IGNORECASE)
BOOKEND_AUTO = "auto"
BOOKEND_SAME = "same"

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


class VoiceTestIn(BaseModel):
    text: str
    voice: str = DEFAULT_VOICE
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    # Voice for sections marked INTRO/OUTRO: "auto" = opposite gender of `voice` in the same
    # language, "same" = no second voice, or an explicit voice id.
    bookend_voice: str = BOOKEND_AUTO


def _tidy(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_story_text(raw: str) -> str:
    """Drops script notes (lines starting with '##') and collapses blank
    lines, so a story file can be pasted as-is."""
    lines = [ln.strip() for ln in raw.splitlines() if not ln.strip().startswith("##")]
    return _tidy("\n".join(lines))


def split_sections(raw: str) -> list[tuple[str, str]]:
    """[(role, text)] in reading order, role in {"intro", "body", "outro"}. Text before any
    section header is body; any other '##' line is a note and is dropped."""
    role = "body"
    buckets: list[tuple[str, list[str]]] = [(role, [])]
    for line in raw.splitlines():
        stripped = line.strip()
        new_role = (
            "intro" if _INTRO_RE.match(stripped)
            else "outro" if _OUTRO_RE.match(stripped)
            else "body" if _BODY_RE.match(stripped)
            else None
        )
        if new_role:
            role = new_role
            buckets.append((role, []))
        elif not stripped.startswith("##"):
            buckets[-1][1].append(stripped)
    sections = [(r, _tidy("\n".join(ls))) for r, ls in buckets]
    return [(r, t) for r, t in sections if t]


def resolve_bookend_voice(main_voice: str, choice: str) -> str:
    if choice == BOOKEND_SAME:
        return main_voice
    if choice != BOOKEND_AUTO:
        return choice
    wanted = "m" if _VOICE_GENDER.get(main_voice) == "f" else "f"
    language = _VOICE_LANGUAGE.get(main_voice)
    for v in VOICES:
        if v["language"] == language and v["gender"] == wanted:
            return v["id"]
    return main_voice


def build_runs(sections: list[tuple[str, str]], main_voice: str, bookend_voice: str) -> list[tuple[str, str]]:
    """[(text, voice_id)], consecutive sections with the same voice merged."""
    runs: list[tuple[str, str]] = []
    for role, text in sections:
        voice = bookend_voice if role in ("intro", "outro") else main_voice
        if runs and runs[-1][1] == voice:
            runs[-1] = (f"{runs[-1][0]}\n\n{text}", voice)
        else:
            runs.append((text, voice))
    return runs


def _output_dir(settings: Settings) -> Path:
    path = Path(settings.library_dir) / "_voice_test"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_job(job_id: str, runs: list[tuple[str, str]], voice: str, speed: float, out_dir: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = out_dir / f".{job_id}.wav"
    mp3_path = out_dir / f"giong-doc_{stamp}_{job_id[:6]}.mp3"
    started = time.time()
    try:
        provider = EdgeTTSProvider()
        language = _VOICE_LANGUAGE.get(voice, "vi")
        if len(runs) == 1:
            result = provider.synthesize(runs[0][0], runs[0][1], language, speed, wav_path)
        else:
            result = synthesize_voice_runs(provider, runs, language, speed, wav_path)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0 or not mp3_path.exists():
            raise RuntimeError(f"Không xuất được MP3: {proc.stderr.strip()}")
        update = {
            "status": "done", "file": str(mp3_path), "path": str(mp3_path), "filename": mp3_path.name,
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
    sections = split_sections(payload.text)
    text = "\n\n".join(t for _, t in sections)
    if not text:
        raise ValidationError("Chưa có nội dung để đọc.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValidationError(f"Truyện quá dài ({len(text)} ký tự, tối đa {MAX_TEXT_CHARS}). Hãy chia nhỏ ra.")
    if payload.voice not in _VOICE_LANGUAGE:
        raise ValidationError(f"Giọng đọc không hỗ trợ: {payload.voice}")
    if payload.bookend_voice not in (BOOKEND_AUTO, BOOKEND_SAME) and payload.bookend_voice not in _VOICE_LANGUAGE:
        raise ValidationError(f"Giọng giới thiệu/kết không hỗ trợ: {payload.bookend_voice}")

    bookend = resolve_bookend_voice(payload.voice, payload.bookend_voice)
    runs = build_runs(sections, payload.voice, bookend)
    has_bookends = any(role in ("intro", "outro") for role, _ in sections)

    job_id = uuid.uuid4().hex
    info = {
        "chars": len(text), "words": len(text.split()),
        "bookend_voice": bookend if has_bookends else None,
        "sections": [role for role, _ in sections],
    }
    with _jobs_lock:
        _jobs[job_id] = {"status": "running", **info}
    threading.Thread(
        target=_run_job, args=(job_id, runs, payload.voice, payload.speed, _output_dir(settings)), daemon=True,
    ).start()
    return {"job_id": job_id, **info}


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


_FILE_NAME_RE = re.compile(r"^giong-doc_[\w-]+\.mp3$")


def _file_path(name: str, settings: Settings) -> Path:
    path = _output_dir(settings) / name
    if not _FILE_NAME_RE.match(name) or not path.is_file():
        raise NotFoundError(f"Không tìm thấy file {name}.")
    return path


@router.get("/voice-test/files")
def list_voice_test_files(settings: Settings = Depends(get_settings)) -> dict:
    """Every MP3 ever produced here (survives restarts, unlike the job list)."""
    folder = _output_dir(settings)
    files = sorted(folder.glob("giong-doc_*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]
    return {
        "folder": str(folder),
        "files": [
            {
                "name": f.name, "path": str(f), "size_kb": round(f.stat().st_size / 1024),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds"),
            }
            for f in files
        ],
    }


@router.get("/voice-test/files/{name}")
def get_voice_test_file(name: str, download: bool = False, settings: Settings = Depends(get_settings)) -> FileResponse:
    return FileResponse(
        _file_path(name, settings), media_type="audio/mpeg", filename=name,
        content_disposition_type="attachment" if download else "inline",
    )


@router.post("/voice-test/open-folder")
def open_voice_test_folder(settings: Settings = Depends(get_settings)) -> dict:
    """Opens the output folder in Windows Explorer (desktop app, local only)."""
    folder = _output_dir(settings)
    os.startfile(str(folder))  # noqa: S606 -- local desktop app, fixed app-owned path
    return {"folder": str(folder)}


@router.get("/voice-test/jobs/{job_id}/audio")
def get_voice_test_audio(job_id: str, download: bool = False) -> FileResponse:
    job = _get_job(job_id)
    if job.get("status") != "done" or not Path(job["file"]).exists():
        raise NotFoundError("File MP3 chưa sẵn sàng.")
    return FileResponse(
        job["file"], media_type="audio/mpeg", filename=job["filename"],
        content_disposition_type="attachment" if download else "inline",
    )
