from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CAPTION_JOB_STATUSES = ("completed", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaptionJob(Base):
    """One caption-generation run for a video -- same synchronous, no-queue
    shape as StoryJob/HookJob.
    """

    __tablename__ = "caption_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    versions: Mapped[list["CaptionVersion"]] = relationship(
        "CaptionVersion", back_populates="job", order_by="CaptionVersion.version_index"
    )


class CaptionVersion(Base):
    """One of the (2, by default) publish-ready content sets produced by a
    single CaptionJob generation call -- Facebook/Instagram/YouTube/pinned
    comment/CTA generated together in one call so they share context.
    """

    __tablename__ = "caption_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    caption_job_id: Mapped[int] = mapped_column(ForeignKey("caption_job.id"), nullable=False)
    version_index: Mapped[int] = mapped_column(Integer, nullable=False)
    facebook_caption: Mapped[str] = mapped_column(String, nullable=False)
    instagram_caption: Mapped[str] = mapped_column(String, nullable=False)
    youtube_description: Mapped[str] = mapped_column(String, nullable=False)
    pinned_comment: Mapped[str] = mapped_column(String, nullable=False)
    cta: Mapped[str] = mapped_column(String, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    job: Mapped[CaptionJob] = relationship("CaptionJob", back_populates="versions")
