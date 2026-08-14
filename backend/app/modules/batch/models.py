"""Batch video production (Task 13 -- see
docs/features/40-batch-video-creation.md): many scripts -> many independent
Projects (app.modules.beat.models.Project) -> the existing RenderQueue
(app.modules.video_composer). This module owns only Batch/BatchItem
bookkeeping -- it never imports app.modules.beat or
app.modules.video_composer (per app/modules/README.md); every reference to
a Project or a VideoComposeJob below is a bare, unconstrained int, the same
"cross-module reference without a real FK" convention already used
throughout this codebase (AIGenerationHistory.job_id,
PublishLog.ai_story_job_id, VideoComposeJob.previous_job_id, etc). The
actual cross-module orchestration (create a Project for each BatchItem,
generate its beats, render it) lives in the composition root --
app/api/v1/endpoints/batch_render.py -- the only place allowed to import
both this module and beat/video_composer at once.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

BATCH_STATUSES = ("DRAFT", "PROCESSING", "COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED")

BATCH_ITEM_STATUSES = (
    "PENDING",
    "PROJECT_CREATED",
    "BEATS_READY",
    "READY_TO_RENDER",
    "RENDERING",
    "COMPLETED",
    "FAILED",
    "SKIPPED",
    "CANCELLED",
)

# Terminal item statuses -- a batch's own coarse status (see
# app/api/v1/endpoints/batch_render.py's _recompute_batch_status) is
# derived from how many items are in these vs. still in flight.
BATCH_ITEM_TERMINAL_STATUSES = ("COMPLETED", "FAILED", "SKIPPED", "CANCELLED")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Batch(Base):
    """One "N scripts in, N projects out" run. `template_id` is a bare
    reference to an app.modules.beat.schemas.Template.id (built-in or
    custom) -- applied once, at creation time, to every item's Project as
    an independent config snapshot (see BatchItem/Project) -- never looked
    up again afterward, so a template changing later can't retroactively
    affect an already-created batch.
    """

    __tablename__ = "batch"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    template_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["BatchItem"]] = relationship("BatchItem", back_populates="batch", order_by="BatchItem.index")


class BatchItem(Base):
    """One script -> one Project -> (eventually) one VideoComposeJob.
    `project_id`/`render_job_id` are bare ints (see module docstring) --
    real FKs are impossible without importing app.modules.beat/
    video_composer, which this module must never do.
    """

    __tablename__ = "batch_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"), nullable=False)
    # 1-based position -- what "001"/"002"/... naming is derived from, the
    # only source of truth for it (never re-derived from array order like
    # Beat.order, since items are never reordered after creation).
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    script_text: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    render_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    batch: Mapped[Batch] = relationship("Batch", back_populates="items")
