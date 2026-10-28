from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.channels.models import PLATFORMS


class ChannelIn(BaseModel):
    platform: str
    name: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    credential: str | None = None

    @field_validator("platform")
    @classmethod
    def _platform(cls, v: str) -> str:
        if v not in PLATFORMS:
            raise ValueError(f"platform must be one of {PLATFORMS}, got {v!r}")
        return v

    @field_validator("name", "external_id")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class ChannelPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    credential: str | None = None


class ChannelOut(BaseModel):
    id: int
    platform: str
    name: str
    external_id: str
    has_credential: bool
    last_synced_at: datetime | None
    last_sync_status: str | None
    last_sync_message: str | None
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "ChannelOut":
        return cls(
            id=row.id,
            platform=row.platform,
            name=row.name,
            external_id=row.external_id,
            has_credential=bool(row.credential),
            last_synced_at=row.last_synced_at,
            last_sync_status=row.last_sync_status,
            last_sync_message=row.last_sync_message,
            created_at=row.created_at,
        )


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    message: str | None


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    followers: int | None
    total_views: int | None
    video_count: int | None
