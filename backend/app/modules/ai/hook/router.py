from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.ai.hook.schemas import HookGenerateIn, HookJobOut, job_to_out
from app.modules.ai.hook.service import HookService
from app.modules.ai.llm_client import resolve_ai_credentials

router = APIRouter()


def get_hook_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HookService:
    return HookService(db, resolve_ai_credentials(settings))


@router.post("/hook-jobs", response_model=HookJobOut, status_code=201)
def create_hook_job(
    payload: HookGenerateIn,
    service: HookService = Depends(get_hook_service),
):
    job = service.generate(video_id=payload.video_id)
    return job_to_out(job)


@router.get("/hook-jobs", response_model=list[HookJobOut])
def list_hook_jobs(
    video_id: int | None = None,
    service: HookService = Depends(get_hook_service),
):
    return [job_to_out(job) for job in service.list_jobs(video_id)]


@router.get("/hook-jobs/{job_id}", response_model=HookJobOut)
def get_hook_job(
    job_id: int,
    service: HookService = Depends(get_hook_service),
):
    return job_to_out(service.get_job(job_id))


@router.post("/hook-jobs/{job_id}/hooks/{hook_id}/favorite", response_model=HookJobOut)
def toggle_hook_favorite(
    job_id: int,
    hook_id: int,
    service: HookService = Depends(get_hook_service),
):
    return job_to_out(service.toggle_favorite(job_id, hook_id))


@router.delete("/hook-jobs/{job_id}", status_code=204)
def delete_hook_job(
    job_id: int,
    service: HookService = Depends(get_hook_service),
):
    service.delete_job(job_id)
