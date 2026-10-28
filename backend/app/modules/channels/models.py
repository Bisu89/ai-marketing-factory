"""Owned-channel management (YouTube / Facebook Page): the channels the
user publishes TO, as opposed to app.models.Channel (source channels
videos are downloaded FROM). Self-contained module: no import of another
module.

`ChannelMetricDaily` is one row per (channel, day), overwritten by later
syncs the same day -- platforms only return the current total, so history
exists only because each day's sync is stored.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PLATFORMS = ("youtube", "facebook")
SYNC_STATUSES = ("running", "ok", "error")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OwnedChannel(Base):
    __tablename__ = "owned_channel"
    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_owned_channel_platform_ext"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # YouTube channel id (UC...) or Facebook Page id.
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    # YouTube Data API key / Facebook Page access token. Local DB only and
    # never returned by the API (schemas expose `has_credential`).
    credential: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String, nullable=True)
    last_sync_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SyncRun(Base):
    __tablename__ = "channel_sync_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("owned_channel.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChannelMetricDaily(Base):
    __tablename__ = "channel_metric_daily"
    __table_args__ = (UniqueConstraint("channel_id", "day", name="uq_channel_metric_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("owned_channel.id", ondelete="CASCADE"), nullable=False, index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL = the platform doesn't expose it (e.g. Facebook total views).
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
