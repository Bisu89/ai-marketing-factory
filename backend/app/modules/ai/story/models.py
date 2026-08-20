from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

STORY_STYLES = ("emotional", "humorous", "inspirational", "dramatic", "educational", "sales")
STORY_LANGUAGES = ("english", "spanish", "vietnamese")
STORY_JOB_STATUSES = ("completed", "failed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StoryJob(Base):
    """One AI-Story generation run for a single library Video. Unlike
    SceneCutJob/VideoComposeJob, this has no background queue/worker -- an LLM
    text-generation call is fast enough (single-digit seconds) to run
    synchronously inside the request, so status is only ever "completed" or
    "failed" by the time the response is returned. Kept as its own table (not
    a column on Video) per the app/modules/ extensibility convention, and
    written purely for history/audit since the epic asked results be saved.
    """

    __tablename__ = "story_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), nullable=False)

    style: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="english")
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # Task 04 -- optional provenance back to the app.modules.content_strategy
    # ContentIdea (if any) that supplied extra context to this generation.
    # Bare int, no FK/relationship -- ai/story must never import
    # content_strategy (per app/modules/README.md); same convention as
    # PublishLog.ai_story_job_id / BatchItem.project_id elsewhere in this
    # codebase. Null for every StoryJob created the plain way (POST
    # /story-jobs with no idea involved), which is most of them.
    content_idea_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    versions: Mapped[list["StoryVersion"]] = relationship(
        "StoryVersion", back_populates="job", order_by="StoryVersion.version_index"
    )


class StoryVersion(Base):
    """One of the (2, by default) narration-script variants produced by a
    single StoryJob generation call.
    """

    __tablename__ = "story_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_job_id: Mapped[int] = mapped_column(ForeignKey("story_job.id"), nullable=False)
    version_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    script_text: Mapped[str] = mapped_column(String, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    job: Mapped[StoryJob] = relationship("StoryJob", back_populates="versions")
