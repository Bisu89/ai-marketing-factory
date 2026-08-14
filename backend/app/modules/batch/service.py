"""Database-backed persistence for Batch/BatchItem -- see models.py's
module docstring for why this module never imports app.modules.beat or
app.modules.video_composer. Mirrors app.modules.beat.project_service's own
"SessionLocal per call" shape for the same reason: called from both
request handlers and a background thread (the batch beat-generation
processor, app/api/v1/endpoints/batch_render.py).
"""

from datetime import datetime, timezone

from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal
from app.modules.batch.models import BATCH_ITEM_TERMINAL_STATUSES, Batch, BatchItem
from app.modules.batch.schemas import parse_scripts

MAX_BATCH_NAME_LEN = 120


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
        _AT_REST = ("PENDING", "PROJECT_CREATED", "BEATS_READY")
        if not statuses:
            new_status = "DRAFT"
        elif any(s == "RENDERING" for s in statuses):
            # Actively rendering right now -- always PROCESSING, even if
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
    "recompute_batch_status",
]
