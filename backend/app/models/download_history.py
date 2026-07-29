from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.video import Video


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DownloadHistory(Base):
    """Append-only log of terminal download outcomes (completed / failed /
    cancelled). Kept separate from download_task so history survives even if
    task rows are ever pruned, and so "how many times has this video been
    attempted" doesn't require inferring it from task.attempts alone.
    """

    __tablename__ = "download_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("download_task.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # completed | failed | cancelled
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    video: Mapped[Video] = relationship("Video", lazy="joined")
