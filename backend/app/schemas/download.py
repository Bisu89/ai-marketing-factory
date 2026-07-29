import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class VideoMetadataIn(BaseModel):
    platform: str
    video_id: str
    channel_name: str
    title: str
    original_url: str | None = None
    thumbnail_url: str | None = None
    views: int | None = None
    likes: int | None = None
    duration_sec: int | None = None
    upload_date: str | None = None
    tags: list[str] = []


class EnqueueRequest(BaseModel):
    url: HttpUrl
    metadata: VideoMetadataIn | None = None


class DownloadJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    url: str
    status: str
    attempts: int
    error_message: str | None

    downloaded_bytes: int
    total_bytes: int | None
    progress_pct: float | None
    speed_bps: float | None
    eta_seconds: float | None

    platform: str | None
    video_id: str | None
    channel_name: str | None
    title: str | None
    original_url: str | None
    thumbnail_url: str | None
    views: int | None
    likes: int | None
    duration_sec: int | None
    upload_date: str | None
    tags: list[str] = Field(default_factory=list, validation_alias="tags_json")
    downloaded_at: datetime | None

    created_at: datetime
    updated_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def _parse_tags(cls, value):
        if isinstance(value, str):
            return json.loads(value or "[]")
        return value or []
