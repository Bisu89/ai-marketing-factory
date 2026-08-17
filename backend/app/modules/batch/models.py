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

# Task 20 (see docs/features/46-factory-batch-engine.md) adds PAUSED (user
# clicked "Pause Batch" -- see factory_pipeline.py's pause_batch_engine)
# and PAUSED_AFTER_RESTART (found "PROCESSING" at application startup --
# see reconcile_batches_on_startup). Both mean "not currently starting new
# work" without claiming any particular terminal outcome -- distinct from
# every existing value, which are all either "not started yet"
# (DRAFT/PROCESSING) or a real outcome (COMPLETED/PARTIAL_FAILURE/FAILED/
# CANCELLED).
BATCH_STATUSES = (
    "DRAFT", "PROCESSING", "PAUSED", "PAUSED_AFTER_RESTART",
    "COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED",
)

BATCH_ITEM_STATUSES = (
    "PENDING",
    "PROJECT_CREATED",
    "BEATS_READY",
    "READY_TO_RENDER",
    # Task 16 (see docs/features/42-content-quality-gate.md) -- the Quality
    # Gate looked at this item's BeatPlan during "Render All" and returned
    # NEEDS_REVIEW (readiness issues, but not a hard blocker); the default
    # batch policy is to skip rendering it, not render it silently. Distinct
    # from SKIPPED, which means "can never render as-is" (BLOCKED, or the
    # existing structural-ineligibility check failed).
    "NEEDS_REVIEW",
    "RENDERING",
    # Task 20 -- the Factory Batch Engine's own single "actively in flight"
    # bucket, covering everything from PREPARING through RENDERING on the
    # underlying FactoryRun (see factory_pipeline.py's _sync_batch_item_from_run).
    # An item starts this flow from PENDING/PROJECT_CREATED/BEATS_READY/
    # READY_TO_RENDER (reusing whatever "not started yet" state it's
    # already in -- e.g. real existing beats are picked up, not
    # regenerated) but only the new engine ever *sets* RUNNING; the old
    # script-based flow's own RENDERING is a separate value it alone uses,
    # so a batch's items never mix the two flows' in-flight markers.
    "RUNNING",
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
    # Indexed (Task 20) -- the Factory Batch Engine's render.job.* handlers
    # look up "which BatchItem does this project belong to" by project_id
    # (see factory_pipeline.py's _find_batch_item_by_project), not just by
    # batch_id, since a render completion event only carries the render
    # job's project via its FactoryRun.
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    render_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    batch: Mapped[Batch] = relationship("Batch", back_populates="items")
