"""Database-backed persistence for ContentBatch/ContentBatchItem -- see
models.py's module docstring for why this module never imports
content_strategy or ai.story. Mirrors app.modules.batch.service's own
"SessionLocal per call" shape for the identical reason: called from both
request handlers and the background worker thread (see
app/api/v1/endpoints/content_batch_generate.py).
"""

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal
from app.modules.content_batch.models import (
    CONTENT_BATCH_ITEM_CLAIMABLE_STATUSES,
    CONTENT_BATCH_ITEM_TERMINAL_STATUSES,
    ContentBatch,
    ContentBatchItem,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_batch(batch_id: int) -> ContentBatch:
    db = SessionLocal()
    try:
        batch = (
            db.query(ContentBatch)
            .options(selectinload(ContentBatch.items))
            .filter(ContentBatch.id == batch_id)
            .first()
        )
        if batch is None:
            raise NotFoundError("Content batch", batch_id)
        db.expunge_all()
        return batch
    finally:
        db.close()


def list_batches() -> list[ContentBatch]:
    db = SessionLocal()
    try:
        batches = (
            db.query(ContentBatch).options(selectinload(ContentBatch.items)).order_by(ContentBatch.id.desc()).all()
        )
        db.expunge_all()
        return batches
    finally:
        db.close()


def set_batch_status(batch_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        batch = db.get(ContentBatch, batch_id)
        if batch is not None:
            batch.status = status
            if status in ("COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED"):
                batch.completed_at = _utcnow()
            db.commit()
    finally:
        db.close()


def set_item_fields(item_id: int, **fields) -> None:
    db = SessionLocal()
    try:
        item = db.get(ContentBatchItem, item_id)
        if item is None:
            return
        for key, value in fields.items():
            setattr(item, key, value)
        db.commit()
    finally:
        db.close()


def claim_item(
    item_id: int,
    new_status: str = "GENERATING",
    from_statuses: tuple[str, ...] = CONTENT_BATCH_ITEM_CLAIMABLE_STATUSES,
) -> bool:
    """Atomic claim -- a single UPDATE with a status-guarded WHERE clause,
    not a read-then-write ORM round trip. Mirrors
    app.modules.batch.service.claim_item exactly (same race-safety
    reasoning: a "Run" click racing a "Retry" click on the same item can
    only ever have one of them see rowcount == 1).
    """
    db = SessionLocal()
    try:
        result = db.execute(
            update(ContentBatchItem)
            .where(ContentBatchItem.id == item_id, ContentBatchItem.status.in_(from_statuses))
            .values(status=new_status)
        )
        db.commit()
        return result.rowcount == 1
    finally:
        db.close()


def bulk_cancel_claimable_items(batch_id: int) -> int:
    """Every item still PENDING becomes CANCELLED immediately and
    atomically -- mirrors app.modules.batch.service.bulk_cancel_claimable_items.
    Items already GENERATING are left alone (an in-flight synchronous AI
    call has no cancellation hook -- same limitation the existing batch
    engine already has); they simply finish and land on whatever terminal
    status they were going to reach anyway.
    """
    db = SessionLocal()
    try:
        result = db.execute(
            update(ContentBatchItem)
            .where(ContentBatchItem.batch_id == batch_id, ContentBatchItem.status.in_(CONTENT_BATCH_ITEM_CLAIMABLE_STATUSES))
            .values(status="CANCELLED")
        )
        db.commit()
        return result.rowcount
    finally:
        db.close()


def recompute_batch_status(batch_id: int) -> str:
    """Derives ContentBatch.status purely from its items' own current
    statuses -- mirrors app.modules.batch.service.recompute_batch_status.
    """
    db = SessionLocal()
    try:
        batch = db.get(ContentBatch, batch_id)
        if batch is None:
            return "DRAFT"
        items = db.query(ContentBatchItem).filter(ContentBatchItem.batch_id == batch_id).all()
        statuses = [item.status for item in items]

        if not statuses:
            new_status = "DRAFT"
        elif any(s in ("PENDING", "GENERATING") for s in statuses):
            new_status = "PROCESSING"
        elif all(s == "CANCELLED" for s in statuses):
            new_status = "CANCELLED"
        elif all(s in CONTENT_BATCH_ITEM_TERMINAL_STATUSES for s in statuses) and any(s == "FAILED" for s in statuses):
            new_status = "FAILED" if all(s == "FAILED" for s in statuses) else "PARTIAL_FAILURE"
        else:
            new_status = "COMPLETED"

        if batch.status != new_status:
            batch.status = new_status
            if new_status in ("COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED"):
                batch.completed_at = _utcnow()
            db.commit()
        return new_status
    finally:
        db.close()
