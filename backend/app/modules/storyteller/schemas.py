from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.storyteller.models import STORYTELLER_ASSET_KINDS


class EpisodeCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    script_text: str = Field(min_length=1)
    voice: str = Field(default="vi-VN-HoaiMyNeural")
    narration_rate: str = Field(default="+0%")
    burn_captions: bool = True
    background_asset_id: int | None = None
    avatar_asset_id: int | None = None

    @field_validator("script_text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("script_text must not be blank")
        return v


class EpisodeOut(BaseModel):
    id: int
    title: str
    word_count: int
    voice: str
    narration_rate: str
    burn_captions: bool
    background_asset_id: int | None
    avatar_asset_id: int | None
    status: str
    progress_stage: str | None
    error_message: str | None
    output_path: str | None
    duration_sec: float | None
    created_at: datetime
    updated_at: datetime


class AssetOut(BaseModel):
    id: int
    kind: str
    name: str
    path: str
    duration_sec: float | None
    width: int | None
    height: int | None
    key_color: str | None
    created_at: datetime


class AssetUploadIn(BaseModel):
    kind: str
    name: str

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, v: str) -> str:
        if v not in STORYTELLER_ASSET_KINDS:
            raise ValueError(f"kind must be one of {STORYTELLER_ASSET_KINDS}")
        return v
