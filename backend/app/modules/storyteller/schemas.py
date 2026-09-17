from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.storyteller.models import STORYTELLER_ASSET_KINDS, STORYTELLER_LAYOUTS


class EpisodeCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    script_text: str = Field(min_length=1)
    voice: str = Field(default="vi-VN-HoaiMyNeural")
    narration_rate: str = Field(default="+0%")
    burn_captions: bool = True
    layout: str = Field(default="single")
    background_asset_id: int | None = None
    avatar_asset_id: int | None = None
    left_asset_id: int | None = None
    middle_asset_id: int | None = None
    right_asset_id: int | None = None
    slide_asset_ids: list[int] | None = None
    disclaimer_text: str | None = Field(default=None, max_length=300)
    story_title: str | None = Field(default=None, max_length=200)
    story_author: str | None = Field(default=None, max_length=200)
    story_character: str | None = Field(default=None, max_length=200)

    @field_validator("script_text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("script_text must not be blank")
        return v

    @field_validator("layout")
    @classmethod
    def _known_layout(cls, v: str) -> str:
        if v not in STORYTELLER_LAYOUTS:
            raise ValueError(f"layout must be one of {STORYTELLER_LAYOUTS}")
        return v

    @model_validator(mode="after")
    def _slideshow_needs_images(self) -> "EpisodeCreateIn":
        if self.layout == "slideshow" and len(self.slide_asset_ids or []) < 2:
            raise ValueError("slideshow layout needs at least 2 slide_asset_ids")
        return self


class EpisodeOut(BaseModel):
    id: int
    title: str
    word_count: int
    voice: str
    narration_rate: str
    burn_captions: bool
    layout: str
    background_asset_id: int | None
    avatar_asset_id: int | None
    left_asset_id: int | None
    middle_asset_id: int | None
    right_asset_id: int | None
    slide_asset_ids: list[int] | None
    disclaimer_text: str | None
    story_title: str | None
    story_author: str | None
    story_character: str | None
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
    media_type: str
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
