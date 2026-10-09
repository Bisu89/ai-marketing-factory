"""Narration segments, TTS generation, master audio. Mounted by router.py."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.modules.documentary.narration import NarrationService
from app.modules.documentary.schemas import (
    NarrationBackendIn,
    NarrationGenerateIn,
    NarrationSegmentOut,
    ReviewOut,
)
from app.modules.documentary.service import DocumentaryService
from app.modules.documentary.tts import available_backends

router = APIRouter()


def _svc(db: Session, settings: Settings) -> DocumentaryService:
    return DocumentaryService(db, library_root=Path(settings.library_dir))


def _narr(db: Session, settings: Settings) -> NarrationService:
    return NarrationService(db, Path(settings.library_dir))


def _out(n: NarrationService, seg) -> NarrationSegmentOut:
    return NarrationSegmentOut(
        segment_key=seg.segment_key, order_index=seg.order_index, text=seg.text, scene_keys=seg.scene_keys,
        status=seg.status, is_current=n.is_current(seg), duration_sec=seg.duration_sec, chars=seg.chars,
        provider=seg.provider, voice=seg.voice, cost_usd=seg.cost_usd, has_word_stamps=bool(seg.word_stamps),
        attempts=seg.attempts, error=seg.error, master_start=seg.master_start, master_end=seg.master_end,
    )


@router.get("/tts-backends")
def tts_backends():
    return {"backends": available_backends()}


@router.post("/projects/{project_id}/narration/plan")
def plan_narration(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _svc(db, settings).plan_narration(project_id)


@router.get("/projects/{project_id}/narration", response_model=list[NarrationSegmentOut])
def list_segments(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _svc(db, settings).get(project_id)
    n = _narr(db, settings)
    return [_out(n, s) for s in n.list(project_id)]


@router.post("/projects/{project_id}/narration/estimate")
def estimate(project_id: int, body: NarrationBackendIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _svc(db, settings).get(project_id)
    return _narr(db, settings).estimate(project_id, body.backend)


@router.post("/projects/{project_id}/narration/generate")
def generate(project_id: int, body: NarrationGenerateIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _svc(db, settings).generate_narration(project_id, body.backend, body.only, body.confirm)


@router.post("/projects/{project_id}/narration/master")
def build_master(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _svc(db, settings).get(project_id)
    return _narr(db, settings).build_master(project_id)


@router.get("/projects/{project_id}/narration/review", response_model=ReviewOut)
def narration_review(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _svc(db, settings).get(project_id)
    issues = _narr(db, settings).review(project_id)
    return ReviewOut(ok=not issues, issues=issues)


@router.get("/projects/{project_id}/narration/master/audio")
def master_audio(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _svc(db, settings).get(project_id)
    path = _narr(db, settings).master_path(project_id)
    if not path.is_file():
        raise NotFoundError("narration master", project_id)
    return FileResponse(path, media_type="audio/wav", filename="narration_master.wav")


@router.get("/projects/{project_id}/narration/{segment_key}/audio")
def segment_audio(project_id: int, segment_key: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _svc(db, settings).get(project_id)
    seg = _narr(db, settings).get(project_id, segment_key)
    if not seg.audio_path or not Path(seg.audio_path).is_file():
        raise NotFoundError("segment audio", segment_key)
    return FileResponse(seg.audio_path)
