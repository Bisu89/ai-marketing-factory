from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.category import Category
from app.models.channel import Channel
from app.models.emotion import Emotion
from app.models.favorite import Favorite
from app.models.platform import Platform
from app.models.tag import Tag

# Content workflow, not download state: a video starts life the moment its
# file lands in the library and moves forward as a person actually curates
# it for publishing. "deleted" is a soft-delete marker outside the visible
# workflow (see VideoLibraryService.delete_video), not a step in it.
VIDEO_STATUSES = ("downloaded", "ready", "published", "archived", "deleted")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    """The canonical, deduplicated record of a video: one row per
    (platform, external_id), regardless of how many times a download for it
    is attempted, and regardless of channel-name spelling variance across
    attempts. is_downloaded/downloaded_at/video_path only get set once a
    download actually completes and the file is organized into library_dir.

    platform_id is intentionally duplicated from channel.platform_id (rather
    than derived purely via the channel join) so the dedup UNIQUE constraint
    and platform filters stay correct/fast without depending on channel_id
    resolution being stable across calls.
    """

    __tablename__ = "video"
    __table_args__ = (UniqueConstraint("platform_id", "external_id", name="uq_video_platform_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platform.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channel.id"), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    original_url: Mapped[str] = mapped_column(String, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String, nullable=True)
    video_path: Mapped[str | None] = mapped_column(String, nullable=True)

    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_date: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="downloaded")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"), nullable=True)
    emotion_id: Mapped[int | None] = mapped_column(ForeignKey("emotion.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
    filesize_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    is_downloaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    platform: Mapped[Platform] = relationship("Platform", lazy="joined")
    channel: Mapped[Channel] = relationship("Channel", lazy="joined")
    category: Mapped[Category | None] = relationship("Category", lazy="joined")
    emotion: Mapped[Emotion | None] = relationship("Emotion", lazy="joined")
    favorite: Mapped[Favorite | None] = relationship("Favorite", lazy="joined", uselist=False)
    tags: Mapped[list[Tag]] = relationship("Tag", secondary="video_tag", lazy="joined")

    @property
    def channel_name(self) -> str:
        return self.channel.name

    @property
    def platform_name(self) -> str:
        return self.platform.name

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None

    @property
    def emotion_name(self) -> str | None:
        return self.emotion.name if self.emotion else None

    @property
    def is_favorite(self) -> bool:
        return self.favorite is not None
