from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.ai.llm_client import resolve_ai_credentials
from app.modules.ai.story.quality import StoryQualityService
from app.modules.ai.story.schemas import StoryGenerateIn, StoryJobOut, StoryVersionOut, job_to_out, version_to_out
from app.modules.ai.story.service import StoryService

router = APIRouter()


def get_story_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StoryService:
    return StoryService(db, resolve_ai_credentials(settings))


def get_story_quality_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StoryQualityService:
    return StoryQualityService(db, resolve_ai_credentials(settings))


@router.post("/story-jobs", response_model=StoryJobOut, status_code=201)
def create_story_job(
    payload: StoryGenerateIn,
    service: StoryService = Depends(get_story_service),
):
    job = service.generate(video_id=payload.video_id, style=payload.style, language=payload.language)
    return job_to_out(job)


@router.get("/story-jobs", response_model=list[StoryJobOut])
def list_story_jobs(
    video_id: int | None = None,
    service: StoryService = Depends(get_story_service),
):
    return [job_to_out(job) for job in service.list_jobs(video_id)]


@router.get("/story-jobs/{job_id}", response_model=StoryJobOut)
def get_story_job(
    job_id: int,
    service: StoryService = Depends(get_story_service),
):
    return job_to_out(service.get_job(job_id))


@router.post("/story-jobs/{job_id}/versions/{version_id}/select", response_model=StoryJobOut)
def select_story_version(
    job_id: int,
    version_id: int,
    service: StoryService = Depends(get_story_service),
):
    return job_to_out(service.select_version(job_id, version_id))


@router.post("/story-jobs/{job_id}/versions/{version_id}/score", response_model=StoryVersionOut)
def score_story_version(
    job_id: int,
    version_id: int,
    service: StoryQualityService = Depends(get_story_quality_service),
):
    """Task 05 -- scores this version on 9 dimensions (Hook/Curiosity/
    Emotion/Conflict/Twist/Ending/Shareability/Originality/Commercial Fit)
    before the (expensive) video pipeline runs. `job_id` in the path is
    for URL consistency with the sibling /select endpoint above -- the
    version_id alone is what's actually scored (a StoryVersion already
    carries its own story_job_id).
    """
    return version_to_out(service.score(version_id))


@router.delete("/story-jobs/{job_id}", status_code=204)
def delete_story_job(
    job_id: int,
    service: StoryService = Depends(get_story_service),
):
    service.delete_job(job_id)
