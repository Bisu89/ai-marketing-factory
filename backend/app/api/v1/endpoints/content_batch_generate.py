"""Task 06 -- Batch Content Generation: many ContentIdeas -> many
Story-generation-and-scoring attempts, run in the background. Composition
root allowed to import content_batch, content_strategy, and ai.story
together (per app/modules/README.md, none of those three may import each
other).

Architecture decision (reported before implementation, per this task's
own "Report architecture decision before implementing a new worker"):
existing AI generation (StoryService.generate/StoryQualityService.score)
is synchronous, single-digit seconds per call. A batch of 20-30 items,
each needing 2 real calls (generate + score), is 40-60 seconds of AI time
at minimum -- unsafe to run inside one HTTP request (timeout, no
progress, no cancel). Rather than building a new queue/worker system,
this reuses the exact pattern already proven in
app/api/v1/endpoints/batch_render.py's own
_run_batch_beat_generation/_generate_beats_for_item: one daemon Thread
per "Run" click, internally a ThreadPoolExecutor bounded by
settings.max_concurrent_ai_generation, each task additionally wrapped in
app.core.concurrency.ai_generation_semaphore (the same process-wide AI
call limiter the existing batch flow and Factory pipeline already share),
each item updating its own row via content_batch.service.set_item_fields,
recompute_batch_status() called once at the end. No new worker
abstraction, no persistent queue table, no second concurrency limiter.

Per this task's own product decision (asked directly, see
docs/features/71-batch-content-generation.md): every item in a batch is
filed under one shared Video (StoryJob.video_id is NOT NULL and a batch
of fresh ContentIdeas has no video of its own yet) -- not 20 separate
videos.
"""

import concurrent.futures
import logging
import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.endpoints.content_idea_generation import _load_idea_context
from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import SessionLocal, get_db
from app.modules.ai.llm_client import AICredentials, resolve_ai_credentials
from app.modules.ai.story.models import QUALITY_SCORE_DIMENSIONS
from app.modules.ai.story.quality import StoryQualityService
from app.modules.ai.story.service import StoryService
from app.modules.content_batch import service as batch_service
from app.modules.content_batch.models import ContentBatch, ContentBatchItem
from app.modules.content_batch.schemas import ContentBatchCreateIn, ContentBatchOut
from app.modules.content_strategy.models import ContentIdea

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_out(batch: ContentBatch) -> ContentBatchOut:
    return ContentBatchOut.model_validate(batch, from_attributes=True)


# -- Create ------------------------------------------------------------


@router.post("/content-batches", response_model=ContentBatchOut, status_code=201)
def create_content_batch(payload: ContentBatchCreateIn, db: Session = Depends(get_db)):
    from app.models.video import Video

    if db.get(Video, payload.video_id) is None:
        raise NotFoundError("Video", payload.video_id)

    ideas = db.query(ContentIdea).filter(ContentIdea.id.in_(payload.idea_ids)).all()
    found_ids = {i.id for i in ideas}
    missing = [i for i in payload.idea_ids if i not in found_ids]
    if missing:
        raise NotFoundError("Content idea", missing[0])

    batch = ContentBatch(
        name=payload.name,
        video_id=payload.video_id,
        style=payload.style,
        language=payload.language,
        score_threshold=payload.score_threshold,
        status="DRAFT",
    )
    db.add(batch)
    db.flush()

    for index, idea_id in enumerate(payload.idea_ids, start=1):
        db.add(ContentBatchItem(batch_id=batch.id, index=index, idea_id=idea_id, status="PENDING"))

    db.commit()
    return _to_out(batch_service.get_batch(batch.id))


# -- List / detail -------------------------------------------------------


@router.get("/content-batches", response_model=list[ContentBatchOut])
def list_content_batches():
    return [_to_out(b) for b in batch_service.list_batches()]


@router.get("/content-batches/{batch_id}", response_model=ContentBatchOut)
def get_content_batch(batch_id: int):
    return _to_out(batch_service.get_batch(batch_id))


# -- Run (bounded-concurrency background thread, see module docstring) ---


def _process_item(
    item_id: int, idea_id: int, video_id: int, style: str, language: str, threshold: float,
    credentials: AICredentials | None,
) -> None:
    db = SessionLocal()
    try:
        if credentials is None:
            batch_service.set_item_fields(
                item_id, status="FAILED",
                error_message="Chua cau hinh AI provider. Vao Settings de chon provider va nhap key.",
            )
            return

        try:
            _idea, context = _load_idea_context(db, idea_id)
        except NotFoundError as exc:
            batch_service.set_item_fields(item_id, status="FAILED", error_message=str(exc))
            return

        story_service = StoryService(db, credentials)
        try:
            job = story_service.generate(
                video_id=video_id, style=style, language=language,
                extra_context=context, content_idea_id=idea_id,
            )
        except Exception as exc:
            logger.exception("Content batch item %s: story generation failed", item_id)
            batch_service.set_item_fields(item_id, status="FAILED", error_message=str(exc))
            return

        version = job.versions[0]
        batch_service.set_item_fields(item_id, story_job_id=job.id, story_version_id=version.id, status="COMPLETED")

        quality_service = StoryQualityService(db, credentials)
        try:
            scored = quality_service.score(version.id)
        except Exception as exc:
            logger.exception("Content batch item %s: scoring failed", item_id)
            # Story generation itself succeeded (preserved -- story_job_id/
            # story_version_id above are already committed) -- only the
            # score is missing, not the whole item's work. "Do not silently
            # discard failed stories": FAILED here still carries a real,
            # inspectable generated story, not nothing.
            batch_service.set_item_fields(item_id, status="FAILED", error_message=f"Cham diem that bai: {exc}")
            return

        average = (scored.quality_score or 0) / len(QUALITY_SCORE_DIMENSIONS)
        final_status = "APPROVED" if average >= threshold else "REJECTED"
        batch_service.set_item_fields(
            item_id, status=final_status, quality_score=scored.quality_score, error_message=None,
        )
    finally:
        db.close()


def _run_batch(batch_id: int, credentials: AICredentials | None, max_workers: int) -> None:
    batch = batch_service.get_batch(batch_id)
    pending = [item for item in batch.items if item.status == "PENDING"]
    if not pending:
        batch_service.recompute_batch_status(batch_id)
        return

    claimed = [item for item in pending if batch_service.claim_item(item.id)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = [
            executor.submit(
                _run_one_with_semaphore,
                item.id, item.idea_id, batch.video_id, batch.style, batch.language, batch.score_threshold,
                credentials,
            )
            for item in claimed
        ]
        concurrent.futures.wait(futures)

    batch_service.recompute_batch_status(batch_id)


def _run_one_with_semaphore(*args) -> None:
    # Task 20's own precedent (see app/core/concurrency.py): the
    # ThreadPoolExecutor's own max_workers already bounds *this batch's*
    # concurrent calls; the shared semaphore additionally bounds the
    # combined total across every AI-calling flow in the process at once
    # (this batch, the script/idea batch flow, the Factory pipeline).
    with ai_generation_semaphore:
        _process_item(*args)


@router.post("/content-batches/{batch_id}/run", response_model=ContentBatchOut)
def run_content_batch(batch_id: int, settings: Settings = Depends(get_settings)):
    batch = batch_service.get_batch(batch_id)
    pending = [item for item in batch.items if item.status == "PENDING"]
    if pending:
        batch_service.set_batch_status(batch_id, "PROCESSING")
        thread = threading.Thread(
            target=_run_batch,
            args=(batch_id, resolve_ai_credentials(settings), settings.max_concurrent_ai_generation),
            daemon=True,
        )
        thread.start()
    return _to_out(batch_service.get_batch(batch_id))


# -- Cancel ----------------------------------------------------------------


@router.post("/content-batches/{batch_id}/cancel", response_model=ContentBatchOut)
def cancel_content_batch(batch_id: int):
    batch_service.get_batch(batch_id)  # 404 if missing
    batch_service.bulk_cancel_claimable_items(batch_id)
    batch_service.recompute_batch_status(batch_id)
    return _to_out(batch_service.get_batch(batch_id))


# -- Retry one failed item ---------------------------------------------------


@router.post("/content-batches/{batch_id}/items/{item_id}/retry", response_model=ContentBatchOut)
def retry_content_batch_item(batch_id: int, item_id: int, settings: Settings = Depends(get_settings)):
    batch = batch_service.get_batch(batch_id)
    item = next((i for i in batch.items if i.id == item_id), None)
    if item is None:
        raise NotFoundError("Content batch item", item_id)

    if not batch_service.claim_item(item_id, new_status="GENERATING", from_statuses=("FAILED",)):
        raise ValidationError("This item cannot be retried right now (not in a FAILED state).")

    batch_service.set_batch_status(batch_id, "PROCESSING")
    credentials = resolve_ai_credentials(settings)
    thread = threading.Thread(
        target=lambda: (
            _run_one_with_semaphore(
                item_id, item.idea_id, batch.video_id, batch.style, batch.language, batch.score_threshold, credentials,
            ),
            batch_service.recompute_batch_status(batch_id),
        ),
        daemon=True,
    )
    thread.start()
    return _to_out(batch_service.get_batch(batch_id))
