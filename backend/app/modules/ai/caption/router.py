from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.ai.caption.schemas import CaptionGenerateIn, CaptionJobOut, job_to_out
from app.modules.ai.caption.service import CaptionService
from app.modules.ai.llm_client import resolve_ai_credentials

router = APIRouter()


def get_caption_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CaptionService:
    return CaptionService(db, resolve_ai_credentials(settings))


@router.post("/caption-jobs", response_model=CaptionJobOut, status_code=201)
def create_caption_job(
    payload: CaptionGenerateIn,
    service: CaptionService = Depends(get_caption_service),
):
    job = service.generate(video_id=payload.video_id)
    return job_to_out(job)


@router.get("/caption-jobs", response_model=list[CaptionJobOut])
def list_caption_jobs(
    video_id: int | None = None,
    service: CaptionService = Depends(get_caption_service),
):
    return [job_to_out(job) for job in service.list_jobs(video_id)]


@router.get("/caption-jobs/{job_id}", response_model=CaptionJobOut)
def get_caption_job(
    job_id: int,
    service: CaptionService = Depends(get_caption_service),
):
    return job_to_out(service.get_job(job_id))


@router.post("/caption-jobs/{job_id}/versions/{version_id}/select", response_model=CaptionJobOut)
def select_caption_version(
    job_id: int,
    version_id: int,
    service: CaptionService = Depends(get_caption_service),
):
    return job_to_out(service.select_version(job_id, version_id))


@router.delete("/caption-jobs/{job_id}", status_code=204)
def delete_caption_job(
    job_id: int,
    service: CaptionService = Depends(get_caption_service),
):
    service.delete_job(job_id)
