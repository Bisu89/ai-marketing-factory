from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

SCENE_CUT_STATUSES = ("queued", "analyzing", "splitting", "completed", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SceneCutJob(Base):
    """One scene-cutting run over a single video: either an existing library
    Video (video_id set) or an arbitrary local file path the user typed in
    (source_path set) -- exactly one of the two, enforced in the service/schema
    layer rather than a DB CHECK constraint (SQLite support for those is
    limited). Its own table, FK'd to video.id only -- per the app/modules/
    extensibility convention, never a column bolted onto Video itself.
    """

    __tablename__ = "scene_cut_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("video.id"), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String, nullable=True)

    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=46.0)
    min_scene_len_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    trim_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    scene_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_dir: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scenes: Mapped[list["SceneCutResult"]] = relationship(
        "SceneCutResult", back_populates="job", order_by="SceneCutResult.scene_number"
    )


class SceneCutResult(Base):
    """One output scene file produced by a completed SceneCutJob."""

    __tablename__ = "scene_cut_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("scene_cut_job.id"), nullable=False)
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_timecode: Mapped[str] = mapped_column(String, nullable=False)
    end_timecode: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)

    job: Mapped[SceneCutJob] = relationship("SceneCutJob", back_populates="scenes")
