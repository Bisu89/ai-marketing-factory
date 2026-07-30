from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

VIDEO_COMPOSE_STATUSES = ("queued", "merging", "finalizing", "completed", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoComposeJob(Base):
    """One "merge many clips into a final video" run: concatenates uploaded
    clips (in user-chosen order) with a swipe-left transition between each
    pair, overlays a fixed title, and optionally mixes in background music.
    Its own table, no FK into the core Video/Channel schema -- these aren't
    Library videos, just standalone compositions -- per the app/modules/
    extensibility convention.

    Narration (TTS) and burned-in karaoke subtitles were part of the first
    version of this feature but were pulled out again to keep the pipeline
    to just "merge with transitions" for now -- see
    docs/features/11-video-composer.md for the reasoning; nothing here
    precludes adding them back as an opt-in step later.
    """

    __tablename__ = "video_compose_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)

    music_path: Mapped[str | None] = mapped_column(String, nullable=True)
    music_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    transition_duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # User-chosen destination folder for the final video. None means "use
    # the default location" (library/_video_composer/job_<id>/output/) --
    # same convention as SceneCutJob.requested_output_dir.
    requested_output_dir: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    output_path: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clips: Mapped[list["VideoComposeClip"]] = relationship(
        "VideoComposeClip", back_populates="job", order_by="VideoComposeClip.position"
    )

    @property
    def clip_count(self) -> int:
        return len(self.clips)


class VideoComposeClip(Base):
    """One input clip for a VideoComposeJob, in merge order (0-based)."""

    __tablename__ = "video_compose_clip"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("video_compose_job.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)

    job: Mapped[VideoComposeJob] = relationship("VideoComposeJob", back_populates="clips")
