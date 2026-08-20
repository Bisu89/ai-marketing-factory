from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.content_strategy.models import CONTENT_IDEA_STATUSES


class PillarCreateIn(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class PillarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class FormatCreateIn(BaseModel):
    pillar_id: int
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class FormatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pillar_id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class IdeaCreateIn(BaseModel):
    pillar_id: int
    format_id: int
    title: str
    premise: str | None = None
    target_emotion_id: int | None = None
    commercial_intent: str | None = None
    status: str = "draft"

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value.strip()

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in CONTENT_IDEA_STATUSES:
            raise ValueError(f"Invalid status {value!r}, must be one of {CONTENT_IDEA_STATUSES}")
        return value


class IdeaUpdateIn(BaseModel):
    title: str | None = None
    premise: str | None = None
    target_emotion_id: int | None = None
    commercial_intent: str | None = None
    score: float | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in CONTENT_IDEA_STATUSES:
            raise ValueError(f"Invalid status {value!r}, must be one of {CONTENT_IDEA_STATUSES}")
        return value


class IdeaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pillar_id: int
    format_id: int
    title: str
    premise: str | None
    target_emotion_id: int | None
    commercial_intent: str | None
    score: float | None
    status: str
    created_at: datetime
    updated_at: datetime
