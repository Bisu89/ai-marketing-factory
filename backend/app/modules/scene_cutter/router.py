from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.modules.scene_cutter.models import SceneCutJob
from app.modules.scene_cutter.schemas import SceneCutJobCreateIn, SceneCutJobOut, job_to_out
from app.modules.scene_cutter.service import SceneCutterService

router = APIRouter()


def get_scene_cutter_service(request: Request) -> SceneCutterService:
    return request.app.state.scene_cutter_service


def _get_job_or_404(db: Session, job_id: int) -> SceneCutJob:
    job = (
        db.query(SceneCutJob)
        .options(selectinload(SceneCutJob.scenes))
        .filter(SceneCutJob.id == job_id)
        .first()
    )
    if job is None:
        raise NotFoundError("Scene cut job", job_id)
    return job


@router.post("/scene-jobs", response_model=SceneCutJobOut, status_code=201)
def create_scene_job(
    payload: SceneCutJobCreateIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: SceneCutterService = Depends(get_scene_cutter_service),
):
    job_id = service.enqueue(
        video_id=payload.video_id,
        source_path=payload.source_path,
        threshold=payload.threshold,
        min_scene_len_sec=payload.min_scene_len_sec,
        trim_sec=payload.trim_sec,
    )
    return job_to_out(_get_job_or_404(db, job_id), Path(settings.library_dir))


@router.get("/scene-jobs", response_model=list[SceneCutJobOut])
def list_scene_jobs(
    video_id: int | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    query = db.query(SceneCutJob).options(selectinload(SceneCutJob.scenes))
    if video_id is not None:
        query = query.filter(SceneCutJob.video_id == video_id)
    jobs = query.order_by(SceneCutJob.id.desc()).all()
    return [job_to_out(job, Path(settings.library_dir)) for job in jobs]


@router.get("/scene-jobs/{job_id}", response_model=SceneCutJobOut)
def get_scene_job(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return job_to_out(_get_job_or_404(db, job_id), Path(settings.library_dir))
