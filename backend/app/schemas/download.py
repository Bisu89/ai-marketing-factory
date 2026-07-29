from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.schemas.video import VideoOut


class PlaylistMetadataIn(BaseModel):
    external_id: str
    title: str


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
    playlist: PlaylistMetadataIn | None = None


class EnqueueRequest(BaseModel):
    url: HttpUrl
    metadata: VideoMetadataIn


class DownloadTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    url: str
    status: str
    attempts: int
    error_message: str | None

    downloaded_bytes: int
    total_bytes: int | None
    progress_pct: float | None
    speed_bps: float | None
    eta_seconds: float | None

    created_at: datetime
    updated_at: datetime

    video: VideoOut
