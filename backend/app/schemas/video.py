from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    platform: str = Field(validation_alias="platform_name")
    external_id: str
    channel_id: int
    channel_name: str
    title: str
    original_url: str
    thumbnail_url: str | None
    thumbnail_path: str | None
    video_path: str | None
    views: int | None
    likes: int | None
    duration_sec: int | None
    upload_date: str | None

    status: str
    category_id: int | None
    notes: str | None
    resolution: str | None
    filesize_bytes: int | None
    file_hash: str | None
    is_favorite: bool
    tags: list[str] = Field(default_factory=list, validation_alias="tag_names")

    is_downloaded: bool
    downloaded_at: datetime | None
    created_at: datetime
    updated_at: datetime
