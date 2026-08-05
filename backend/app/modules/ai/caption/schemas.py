from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.ai.caption.models import CaptionJob


class CaptionGenerateIn(BaseModel):
    video_id: int


class CaptionVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_index: int
    facebook_caption: str
    instagram_caption: str
    youtube_description: str
    pinned_comment: str
    cta: str
    is_selected: bool


class CaptionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    status: str
    error_message: str | None
    created_at: datetime
    versions: list[CaptionVersionOut] = []


def job_to_out(job: CaptionJob) -> CaptionJobOut:
    return CaptionJobOut.model_validate(job)
