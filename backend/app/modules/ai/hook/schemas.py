from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.ai.hook.models import HookJob


class HookGenerateIn(BaseModel):
    video_id: int


class HookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hook_index: int
    text: str
    is_favorite: bool


class HookJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    status: str
    error_message: str | None
    created_at: datetime
    hooks: list[HookOut] = []


def job_to_out(job: HookJob) -> HookJobOut:
    return HookJobOut.model_validate(job)
