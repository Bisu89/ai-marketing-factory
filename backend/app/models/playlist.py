from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Playlist(Base):
    __tablename__ = "playlist"
    __table_args__ = (UniqueConstraint("platform", "external_id", name="uq_playlist_platform_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channel.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class PlaylistVideo(Base):
    """Many-to-many join: a video can appear in multiple playlists."""

    __tablename__ = "playlist_video"

    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlist.id"), primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
