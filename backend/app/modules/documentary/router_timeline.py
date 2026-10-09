"""Alignment, scene timeline and subtitles. Mounted by router.py."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.documentary import align_whisper
from app.modules.documentary.schemas import ReviewOut
from app.modules.documentary.service import DocumentaryService
from app.modules.documentary.timeline import TimelineService

router = APIRouter()


class AlignIn(BaseModel):
    method: Literal["auto", "tts", "whisper", "estimated"] = "auto"
    only: list[str] | None = None


class SceneStartIn(BaseModel):
    start: float = Field(ge=0)


class SceneTimingOut(BaseModel):
    scene_key: str
    order_index: int
    start: float
    end: float
    duration: float
    source: str
    coverage: float
    needs_review: bool


class SubtitleOut(BaseModel):
    order_index: int
    start: float
    end: float
    text: str
    scene_key: str | None
    source: str


def _tl(db: Session, settings: Settings) -> TimelineService:
    return TimelineService(db, Path(settings.library_dir))


def _check(db: Session, settings: Settings, project_id: int) -> TimelineService:
    DocumentaryService(db, library_root=Path(settings.library_dir)).get(project_id)
    return _tl(db, settings)


@router.get("/alignment-status")
def alignment_status(settings: Settings = Depends(get_settings)):
    return {"whisper_installed": align_whisper.is_available(), "whisper_model": settings.documentary_whisper_model}


@router.post("/projects/{project_id}/timeline/align")
def align(project_id: int, body: AlignIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _check(db, settings, project_id).align(project_id, body.method, body.only)


@router.post("/projects/{project_id}/timeline/assemble")
def assemble(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _check(db, settings, project_id).assemble(project_id)


@router.get("/projects/{project_id}/timeline", response_model=list[SceneTimingOut])
def timeline(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    tl = _check(db, settings, project_id)
    return [
        SceneTimingOut(
            scene_key=t.scene_key, order_index=t.order_index, start=t.start, end=t.end, duration=round(t.end - t.start, 3),
            source=t.source, coverage=t.coverage, needs_review=t.needs_review,
        )
        for t in tl.timings(project_id)
    ]


@router.put("/projects/{project_id}/timeline/scenes/{scene_key}/start")
def set_scene_start(
    project_id: int, scene_key: str, body: SceneStartIn, db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return _check(db, settings, project_id).set_scene_start(project_id, scene_key, body.start)


@router.delete("/projects/{project_id}/timeline/scenes/{scene_key}/start")
def clear_scene_start(project_id: int, scene_key: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _check(db, settings, project_id).clear_override(project_id, scene_key)


@router.get("/projects/{project_id}/timeline/review", response_model=ReviewOut)
def timeline_review(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _check(db, settings, project_id).review(project_id)


@router.get("/projects/{project_id}/subtitles", response_model=list[SubtitleOut])
def subtitles(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    tl = _check(db, settings, project_id)
    return [
        SubtitleOut(order_index=s.order_index, start=s.start, end=s.end, text=s.text, scene_key=s.scene_key, source=s.source)
        for s in tl.subtitles(project_id)
    ]


@router.get("/projects/{project_id}/subtitles.srt")
def subtitles_srt(project_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    tl = _check(db, settings, project_id)
    return Response(
        content=tl.srt(project_id).encode("utf-8"),
        media_type="application/x-subrip; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="documentary_{project_id}.srt"'},
    )
