"""Pydantic I/O + status validation for the Publishing module. Pure -- no
DB/FastAPI/other-module dependency.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.publishing.models import UPLOAD_JOB_STATUSES, YOUTUBE_PRIVACY_STATUSES


class YouTubeChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: str
    title: str
    thumbnail_url: str | None
    enabled: bool
    last_error: str | None
    created_at: datetime | None = None
    # Filled in by the router, not stored: how many completed uploads this
    # channel has.
    upload_count: int | None = None


class YouTubeChannelUpdateIn(BaseModel):
    enabled: bool | None = None


class OAuthAuthorizeUrlOut(BaseModel):
    authorize_url: str


class YouTubeUploadJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_pk: int
    channel_title: str | None = None
    project_id: int
    status: str
    requested_privacy: str
    title: str | None
    youtube_video_id: str | None
    watch_url: str | None = None
    error_message: str | None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class UploadRequest(BaseModel):
    project_id: int
    channel_id: int  # YouTubeChannel.id (local pk)
    privacy: str = "private"

    @field_validator("privacy")
    @classmethod
    def _known_privacy(cls, value: str) -> str:
        if value not in YOUTUBE_PRIVACY_STATUSES:
            raise ValueError(f"privacy must be one of {YOUTUBE_PRIVACY_STATUSES}")
        return value


class UploadResponse(BaseModel):
    upload_job_id: int
    status: str


assert set(UPLOAD_JOB_STATUSES) >= {"pending", "uploading", "completed", "failed"}
