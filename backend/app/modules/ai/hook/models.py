from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

HOOK_JOB_STATUSES = ("completed", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HookJob(Base):
    """One hook-generation run for a video -- same synchronous, no-queue
    shape as StoryJob (see app/modules/ai/story/models.py). "Regenerate" is
    just calling generate() again, producing a new HookJob rather than
    mutating an old one, so past batches stay around to compare.
    """

    __tablename__ = "hook_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    hooks: Mapped[list["HookVersion"]] = relationship(
        "HookVersion", back_populates="job", order_by="HookVersion.hook_index"
    )


class HookVersion(Base):
    __tablename__ = "hook_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    hook_job_id: Mapped[int] = mapped_column(ForeignKey("hook_job.id"), nullable=False)
    hook_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    job: Mapped[HookJob] = relationship("HookJob", back_populates="hooks")
