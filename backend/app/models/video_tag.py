from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoTag(Base):
    """Many-to-many join: a video can have multiple tags, a tag can apply to
    multiple videos."""

    __tablename__ = "video_tag"

    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
