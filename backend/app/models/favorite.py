from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Favorite(Base):
    """Presence of a row == the video is favorited. video_id is both the PK
    and the FK, giving a natural one-to-one with Video (single-user app --
    if multi-user support is ever added, add a user_id column and change the
    PK to (user_id, video_id))."""

    __tablename__ = "favorite"

    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
