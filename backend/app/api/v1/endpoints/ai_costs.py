"""Task 10 -- AI Cost Tracking. Composition root: the one place allowed to
import app.modules.ai.cost_service together with app.modules.content_batch
(cost per batch) and app.modules.factory/app.modules.video_composer (AI
image generation cost + "videos generated"), per app/modules/README.md.

"Videos Generated" / "Cost per Video" use VideoComposeJob's own completed
count -- the app's one existing definition of "a produced video" (see
Task 43's Production Dashboard, dashboard.py's own recent_completed_jobs).
Cost per video only ever includes AI Image Generation cost
(FactoryRun.visual_generation_cost_usd, joined via
FactoryRun.render_job_id == VideoComposeJob.id) -- Story/Hook/Caption/
Scoring costs have no link path to a specific VideoComposeJob in this
codebase today (StoryJob only ever carries a Library video_id, never a
Project/FactoryRun id), so they are counted in full in
total_ai_cost_usd/by_provider/by_model/by_month but deliberately NOT
folded into average_cost_per_video_usd -- doing so would silently
misattribute a cost with no real link. A genuine product decision,
confirmed with the user before building this -- see
docs/features/75-ai-cost-tracking.md.

Read-only throughout -- no endpoint here writes anything.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.ai import cost_service
from app.modules.ai.image_client import IMAGE_MODEL
from app.modules.content_batch.models import ContentBatch, ContentBatchItem
from app.modules.factory.models import FactoryRun
from app.modules.video_composer.models import VideoComposeJob
from app.schemas.ai_cost import (
    AICallCostOut,
    AICostSummaryOut,
    BatchCostOut,
    GroupCostOut,
    StoryCostOut,
    VideoCostOut,
)

router = APIRouter()

_IMAGE_PROVIDER = "openai"


def _image_group_costs(db: Session, key_fn) -> dict[str, tuple[float, int]]:
    """label -> (total_cost_usd, run_count) for every FactoryRun with a
    real AI-image-generation cost. visual_generation_cost_usd is NULL for
    every "library" mode run (see FactoryRun's own docstring), so those
    are naturally excluded, never counted as $0.
    """
    runs = db.query(FactoryRun).filter(FactoryRun.visual_generation_cost_usd.isnot(None)).all()
    buckets: dict[str, list[float]] = {}
    for run in runs:
        buckets.setdefault(key_fn(run), []).append(run.visual_generation_cost_usd)
    return {label: (round(sum(costs), 6), len(costs)) for label, costs in buckets.items()}


def _merge_groups(text_groups: list[cost_service.GroupCost], image_costs: dict[str, tuple[float, int]]) -> list[GroupCostOut]:
    merged: dict[str, GroupCostOut] = {
        g.label: GroupCostOut(
            label=g.label,
            total_cost_usd=g.total_cost_usd,
            call_count=g.call_count,
            unpriced_call_count=g.unpriced_call_count,
            all_confirmed=g.all_confirmed,
        )
        for g in text_groups
    }
    for label, (cost, count) in image_costs.items():
        existing = merged.get(label)
        if existing is None:
            merged[label] = GroupCostOut(
                label=label, total_cost_usd=cost, call_count=count, unpriced_call_count=0, all_confirmed=True
            )
        else:
            merged[label] = GroupCostOut(
                label=label,
                total_cost_usd=round(existing.total_cost_usd + cost, 6),
                call_count=existing.call_count + count,
                unpriced_call_count=existing.unpriced_call_count,
                all_confirmed=existing.all_confirmed,
            )
    return sorted(merged.values(), key=lambda g: g.total_cost_usd, reverse=True)


# -- Summary -----------------------------------------------------------


@router.get("/ai-costs/summary", response_model=AICostSummaryOut)
def cost_summary(db: Session = Depends(get_db)):
    calls = cost_service.all_call_costs(db)
    total_text_cost = round(sum(c.cost_usd for c in calls if c.cost_usd is not None), 6)
    unpriced_call_count = sum(1 for c in calls if c.cost_usd is None)

    image_runs = db.query(FactoryRun).filter(FactoryRun.visual_generation_cost_usd.isnot(None)).all()
    total_image_cost = round(sum(r.visual_generation_cost_usd for r in image_runs), 6)

    completed_job_ids = {j.id for j in db.query(VideoComposeJob.id).filter(VideoComposeJob.status == "completed").all()}
    videos_generated = len(completed_job_ids)
    attributable_image_cost = round(
        sum(r.visual_generation_cost_usd for r in image_runs if r.render_job_id in completed_job_ids), 6
    )

    if videos_generated == 0:
        average_cost_per_video_usd = None
        avg_note = "Chưa có video nào render xong (VideoComposeJob completed) để tính trung bình."
    else:
        average_cost_per_video_usd = round(attributable_image_cost / videos_generated, 6)
        avg_note = (
            "Chỉ gồm chi phí AI Image Generation gắn với video đã render xong. Chi phí Story/Hook/Caption/"
            "Scoring không có đường nối tới một VideoComposeJob cụ thể nên không cộng vào đây -- vẫn có "
            "đầy đủ trong AI Cost tổng và Cost by Provider/Model bên dưới."
        )

    by_provider = _merge_groups(cost_service.cost_by_provider(calls), _image_group_costs(db, lambda r: _IMAGE_PROVIDER))
    by_model = _merge_groups(
        cost_service.cost_by_model(calls), _image_group_costs(db, lambda r: f"{_IMAGE_PROVIDER}/{IMAGE_MODEL}")
    )
    by_month = _merge_groups(
        cost_service.cost_by_month(calls), _image_group_costs(db, lambda r: r.created_at.strftime("%Y-%m"))
    )

    return AICostSummaryOut(
        total_ai_cost_usd=round(total_text_cost + total_image_cost, 6),
        total_calls=len(calls),
        unpriced_call_count=unpriced_call_count,
        videos_generated=videos_generated,
        average_cost_per_video_usd=average_cost_per_video_usd,
        average_cost_per_video_note=avg_note,
        cost_per_1000_videos_usd=(round(average_cost_per_video_usd * 1000, 4) if average_cost_per_video_usd is not None else None),
        by_provider=by_provider,
        by_model=by_model,
        by_month=by_month,
    )


# -- Cost per AI call ----------------------------------------------------


@router.get("/ai-costs/calls", response_model=list[AICallCostOut])
def cost_by_call(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    calls = cost_service.all_call_costs(db)
    return list(reversed(calls))[:limit]


# -- Cost per story -------------------------------------------------------


@router.get("/ai-costs/stories", response_model=list[StoryCostOut])
def cost_by_story(db: Session = Depends(get_db)):
    calls = cost_service.all_call_costs(db)
    return cost_service.cost_by_story(db, calls)


# -- Cost per batch (app.modules.content_batch) ----------------------------


@router.get("/ai-costs/batches", response_model=list[BatchCostOut])
def cost_by_batch(db: Session = Depends(get_db)):
    calls = cost_service.all_call_costs(db)
    story_costs = {s.story_job_id: s for s in cost_service.cost_by_story(db, calls)}

    batches = db.query(ContentBatch).all()
    items_by_batch: dict[int, list[ContentBatchItem]] = {}
    for item in db.query(ContentBatchItem).all():
        items_by_batch.setdefault(item.batch_id, []).append(item)

    results = []
    for batch in batches:
        total = 0.0
        story_count = 0
        unpriced = 0
        for item in items_by_batch.get(batch.id, []):
            if item.story_job_id is None:
                continue
            sc = story_costs.get(item.story_job_id)
            if sc is None:
                continue
            total += sc.total_cost_usd
            story_count += 1
            unpriced += sc.unpriced_call_count
        results.append(
            BatchCostOut(
                batch_id=batch.id,
                batch_name=batch.name,
                total_cost_usd=round(total, 6),
                story_count=story_count,
                unpriced_call_count=unpriced,
            )
        )
    results.sort(key=lambda b: b.total_cost_usd, reverse=True)
    return results


# -- Cost per produced video (app.modules.video_composer/factory) -----------


@router.get("/ai-costs/videos", response_model=list[VideoCostOut])
def cost_by_video(db: Session = Depends(get_db)):
    completed = (
        db.query(VideoComposeJob).filter(VideoComposeJob.status == "completed").order_by(VideoComposeJob.created_at.desc()).all()
    )
    runs_by_render_job = {r.render_job_id: r for r in db.query(FactoryRun).filter(FactoryRun.render_job_id.isnot(None)).all()}

    results = []
    for job in completed:
        run = runs_by_render_job.get(job.id)
        results.append(
            VideoCostOut(
                video_compose_job_id=job.id,
                project_id=run.project_id if run else None,
                image_cost_usd=run.visual_generation_cost_usd if run else None,
                image_count=run.visual_generation_image_count if run else None,
            )
        )
    return results
