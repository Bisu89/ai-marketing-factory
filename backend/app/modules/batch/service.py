"""Database-backed persistence for Batch/BatchItem -- see models.py's
module docstring for why this module never imports app.modules.beat or
app.modules.video_composer. Mirrors app.modules.beat.project_service's own
"SessionLocal per call" shape for the same reason: called from both
request handlers and a background thread (the batch beat-generation
processor, app/api/v1/endpoints/batch_render.py).
"""

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal
from app.modules.batch.models import BATCH_ITEM_TERMINAL_STATUSES, Batch, BatchItem
from app.modules.batch.schemas import parse_scripts

MAX_BATCH_NAME_LEN = 120

# Task 20 (see docs/features/46-factory-batch-engine.md) -- statuses the
# Factory Batch Engine may claim an item *from*. Deliberately excludes
# NEEDS_REVIEW/FAILED (those only ever restart via an explicit "Continue
# Ready"/"Retry Failed" action, never the normal scheduling pass -- section
# 15/45) and every terminal status.
BATCH_ITEM_ENGINE_CLAIMABLE_STATUSES = ("PENDING", "PROJECT_CREATED", "BEATS_READY", "READY_TO_RENDER")


def project_name_for_item(batch_name: str, index: int) -> str:
    """"Emotional Stories August" + 3 -> "Emotional Stories August 003" --
    see docs/features/40-batch-video-creation.md section 11. Zero-padded
    to 3 digits regardless of batch size (matches the brief's own examples;
    a >999-item batch is not a real scenario this tool targets).
    """
    return f"{batch_name.strip()} {index:03d}"


def get_batch(batch_id: int) -> Batch:
    db = SessionLocal()
    try:
        batch = (
            db.query(Batch).options(selectinload(Batch.items)).filter(Batch.id == batch_id).first()
        )
        if batch is None:
            raise NotFoundError("Batch", batch_id)
        db.expunge_all()
        return batch
    finally:
        db.close()


def list_batches() -> list[Batch]:
    db = SessionLocal()
    try:
        batches = (
            db.query(Batch).options(selectinload(Batch.items)).order_by(Batch.id.desc()).all()
        )
        db.expunge_all()
        return batches
    finally:
        db.close()


def set_batch_status(batch_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        batch = db.get(Batch, batch_id)
        if batch is not None:
            batch.status = status
            db.commit()
    finally:
        db.close()


def set_item_fields(item_id: int, **fields) -> None:
    db = SessionLocal()
    try:
        item = db.get(BatchItem, item_id)
        if item is None:
            return
        for key, value in fields.items():
            setattr(item, key, value)
        db.commit()
    finally:
        db.close()


def claim_item(
    item_id: int, new_status: str = "RUNNING", from_statuses: tuple[str, ...] = BATCH_ITEM_ENGINE_CLAIMABLE_STATUSES
) -> bool:
    """Task 20 section 27/28's own "atomic claim" -- a single UPDATE with a
    status-guarded WHERE clause, not a read-then-write ORM round trip. Two
    overlapping scheduling passes (a manual "Run Batch" click racing
    startup recovery, a retry racing the engine's own next tick, etc.)
    calling this for the same item can only ever have one of them see
    rowcount == 1; the loser gets False and must not start any work.

    `from_statuses` defaults to the normal scheduling pass's own claimable
    set, but "Continue Ready" (NEEDS_REVIEW -> RUNNING) and "Retry Failed"
    (FAILED -> RUNNING) are distinct, narrower claims -- see
    factory_pipeline.py's continue_batch_factory/retry_batch_failed --
    reusing this same atomic primitive rather than a second one.
    """
    db = SessionLocal()
    try:
        result = db.execute(
            update(BatchItem)
            .where(BatchItem.id == item_id, BatchItem.status.in_(from_statuses))
            .values(status=new_status)
        )
        db.commit()
        return result.rowcount == 1
    finally:
        db.close()


def get_batch_item_by_project(project_id: int) -> BatchItem | None:
    """Reverse lookup used by the Factory Batch Engine's render.job.*
    handlers (see factory_pipeline.py) -- a render completion event only
    carries a job id / the FactoryRun's project_id, never a batch_id.
    Indexed on BatchItem.project_id (Task 20 -- see models.py).
    """
    db = SessionLocal()
    try:
        item = db.query(BatchItem).filter(BatchItem.project_id == project_id).order_by(BatchItem.id.desc()).first()
        if item is not None:
            db.expunge(item)
        return item
    finally:
        db.close()


def bulk_cancel_claimable_items(batch_id: int) -> int:
    """Task 20 section 23/24: every item still in a claimable ("not started
    yet") status becomes CANCELLED immediately and atomically -- this is
    also what makes cancellation safe against a concurrently-running
    engine tick: by the time any in-flight claim_item() call reaches this
    item, it will no longer be in a claimable status, so the claim simply
    fails (returns False) rather than racing a "start after cancel" bug.
    Returns how many items were actually cancelled.
    """
    db = SessionLocal()
    try:
        result = db.execute(
            update(BatchItem)
            .where(BatchItem.batch_id == batch_id, BatchItem.status.in_(BATCH_ITEM_ENGINE_CLAIMABLE_STATUSES))
            .values(status="CANCELLED")
        )
        db.commit()
        return result.rowcount
    finally:
        db.close()


def recompute_batch_status(batch_id: int) -> str:
    """Derives Batch.status purely from its items' own current statuses --
    never a separately-tracked flag that could drift. Called after every
    item status change (beat generation, render enqueue/completion,
    cancel, retry) so Batch.status is always an accurate reflection, not a
    snapshot from whenever the batch was last touched.
    """
    db = SessionLocal()
    try:
        batch = db.get(Batch, batch_id)
        if batch is None:
            return "DRAFT"
        items = db.query(BatchItem).filter(BatchItem.batch_id == batch_id).all()
        statuses = [item.status for item in items]

        # Order matters -- each branch below is checked only after the
        # previous ones ruled it out:
        # NEEDS_REVIEW (Task 16 -- see docs/features/42-content-quality-gate.md)
        # is "waiting for a human to look at it," the same at-rest shape as
        # BEATS_READY (not yet rendered, not a permanent failure).
        _AT_REST = ("PENDING", "PROJECT_CREATED", "BEATS_READY", "NEEDS_REVIEW")
        if not statuses:
            new_status = "DRAFT"
        elif any(s in ("RENDERING", "RUNNING") for s in statuses):
            # Actively rendering (old script-based flow) or actively
            # progressing through a FactoryRun (Task 20's batch engine, see
            # factory_pipeline.py) right now -- always PROCESSING, even if
            # some other item already failed/completed; that's still
            # active work in flight.
            new_status = "PROCESSING"
        elif all(s == "CANCELLED" for s in statuses):
            new_status = "CANCELLED"
        elif all(s in _AT_REST for s in statuses):
            # Created and/or beats generated, nothing rendering, nothing
            # permanently failed yet -- prepared and waiting for the next
            # explicit user action (Generate Beats / Render All). Task 13's
            # own status vocabulary has no separate "READY" state, so DRAFT
            # covers this whole pre-render preparation window, not just
            # "just created."
            new_status = "DRAFT"
        elif all(s in BATCH_ITEM_TERMINAL_STATUSES for s in statuses):
            if all(s == "COMPLETED" for s in statuses):
                new_status = "COMPLETED"
            elif any(s == "COMPLETED" for s in statuses):
                new_status = "PARTIAL_FAILURE"
            else:
                new_status = "FAILED"
        else:
            # A genuine mix: some FAILED/SKIPPED (a permanent problem)
            # alongside some still-in-prep items -- surfaced as
            # PARTIAL_FAILURE immediately so the problem is visible without
            # waiting for the rest of the batch to also finish.
            new_status = "PARTIAL_FAILURE" if any(s in ("FAILED", "SKIPPED") for s in statuses) else "DRAFT"

        batch.status = new_status
        if new_status in ("COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED") and batch.completed_at is None:
            batch.completed_at = datetime.now(timezone.utc)
        elif new_status == "PROCESSING":
            batch.completed_at = None
        db.commit()
        return new_status
    finally:
        db.close()


__all__ = [
    "parse_scripts",
    "project_name_for_item",
    "get_batch",
    "list_batches",
    "set_batch_status",
    "set_item_fields",
    "claim_item",
    "get_batch_item_by_project",
    "bulk_cancel_claimable_items",
    "recompute_batch_status",
]
