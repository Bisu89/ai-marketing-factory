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

    `ai_story_job_id`/`story_style` are free-form traceability fields the
    user can fill in manually; the AI Story generator module and the
    Insights CSV-import feature that used to populate/link these were
    removed (see docs/features/63-remove-ai-content-and-insights.md).
    `post_id`/`page_id` are dormant leftovers from that removed Insights
    linking feature -- kept on the model (SQLite has no migration
    framework to drop them) but no longer set or read by any code.
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
