from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.content_batch.models import CONTENT_BATCH_ITEM_STATUSES, CONTENT_BATCH_STATUSES


class ContentBatchCreateIn(BaseModel):
    name: str
    video_id: int
    idea_ids: list[int]
    style: str
    language: str = "english"
    score_threshold: float = 8.0

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @field_validator("idea_ids")
    @classmethod
    def _idea_ids_not_empty(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("idea_ids must not be empty")
        return value

    @field_validator("score_threshold")
    @classmethod
    def _threshold_in_range(cls, value: float) -> float:
        if not (0 <= value <= 10):
            raise ValueError(f"score_threshold must be between 0 and 10, got {value}")
        return value


class ContentBatchItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    index: int
    idea_id: int
    story_job_id: int | None
    story_version_id: int | None
    quality_score: float | None
    status: str
    error_message: str | None
    created_at: datetime

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in CONTENT_BATCH_ITEM_STATUSES:
            raise ValueError(f"Invalid status {value!r}")
        return value


class ContentBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    video_id: int
    style: str
    language: str
    score_threshold: float
    status: str
    created_at: datetime
    completed_at: datetime | None
    items: list[ContentBatchItemOut] = []

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in CONTENT_BATCH_STATUSES:
            raise ValueError(f"Invalid status {value!r}")
        return value
