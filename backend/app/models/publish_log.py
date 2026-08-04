from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.video import Video

PUBLISH_LOG_STATUSES = ("none", "winner", "loser", "archived")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PublishLog(Base):
    """Records that a Library Video was published somewhere, plus the
    creative/business metadata that can never be extracted from a platform's
    own analytics export (hook_type, story_style, ai_story_job_id,
    affiliate_*) -- see docs/features/15-performance-intelligence.md.

    `ai_story_job_id` is a plain int, deliberately NOT an ORM
    relationship/FK constraint into app.modules.story -- per
    app/modules/README.md, core (this file) must never import from a
    module. The frontend resolves the actual StoryJob/StoryVersion via the
    module's own existing API (GET /story-jobs?video_id=) when building the
    publish-log form; this column is a bare traceability reference only.

    `post_id`/`page_id` link this row to a real InsightPostSnapshot
    (app/models/insight_post.py) -- set later via an explicit user action on
    the Insights page, not at creation time, since a PublishLog is usually
    created before any matching CSV data has been uploaded. Linking by
    post_id (stable across every snapshot of the same real-world post)
    rather than a video_id column on InsightPostSnapshot itself means one
    link covers all past and future snapshots of that post.
    """

    __tablename__ = "publish_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), nullable=False)

    platform: Mapped[str] = mapped_column(String, nullable=False, default="facebook")
    page_name: Mapped[str | None] = mapped_column(String, nullable=True)

    hook_type: Mapped[str | None] = mapped_column(String, nullable=True)
    story_style: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_story_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    affiliate_product: Mapped[str | None] = mapped_column(String, nullable=True)
    affiliate_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affiliate_sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affiliate_revenue: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str] = mapped_column(String, nullable=False, default="none")

    post_id: Mapped[str | None] = mapped_column(String, nullable=True)
    page_id: Mapped[str | None] = mapped_column(String, nullable=True)

    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    video: Mapped[Video] = relationship("Video", lazy="joined")
