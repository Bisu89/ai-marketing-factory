"""Task 09 -- AI Content Learning Loop. Composition root, same shape as
Task 07/08's performance_intelligence.py/winner_detection.py: the one
place allowed to import app.services.insights together with
app.modules.ai.story/app.modules.content_strategy, needed for the
Pillar/Format/Emotion dimensions (PublishLog.ai_story_job_id ->
StoryJob.content_idea_id -> ContentIdea.pillar_id/format_id/
target_emotion_id).

New system this task describes:
    Historical Performance -> Pattern Weights -> Idea Generation -> Story/Hook Generation
"Pattern Weights" = winner_detection_service's WinnerGroupStats/TrendGroupStats
(Task 08, reused untouched) fed into recommendation_service's transparent
weight formula (Task 09, new). This endpoint answers "what should we
generate next" -- it never calls any generation endpoint itself. Nothing
here writes anything; a recommendation is read-only advice a human (or a
future explicit "apply" action, not built here) acts on, never something
that silently steers POST /content-ideas/generate-story or the batch
flow -- see docs/features/74-content-learning-loop.md's own "do not
silently manipulate generation" note.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.emotion import Emotion
from app.models.publish_log import PublishLog
from app.modules.ai.story.models import StoryJob
from app.modules.content_strategy.models import ContentFormat, ContentIdea, ContentPillar
from app.schemas.recommendation import RecommendationOut
from app.services.insights.performance_service import PerformanceService
from app.services.insights.recommendation_service import rank_recommendations
from app.services.insights.winner_detection_service import (
    DEFAULT_MIN_SAMPLE_SIZE,
    compute_group_stats,
    compute_trends,
    key_by_duration,
)

router = APIRouter()

DIMENSIONS = ("pillar", "format", "hook", "emotion")


def _resolve_pillar_format_emotion(db: Session, ai_story_job_id: int | None) -> tuple[str | None, str | None, str | None]:
    """Same chain as performance_intelligence.py's own _resolve_pillar_format
    (StoryJob.content_idea_id -> ContentIdea -> Pillar/Format), extended
    with target_emotion_id -> Emotion.name for this task's own required
    "winning emotional patterns" dimension. A fresh, self-contained
    resolver rather than editing that already-verified function, to avoid
    any risk to Task 07/08's own tested behavior.
    """
    if ai_story_job_id is None:
        return None, None, None
    job = db.get(StoryJob, ai_story_job_id)
    if job is None or job.content_idea_id is None:
        return None, None, None
    idea = db.get(ContentIdea, job.content_idea_id)
    if idea is None:
        return None, None, None
    pillar = db.get(ContentPillar, idea.pillar_id)
    fmt = db.get(ContentFormat, idea.format_id)
    emotion = db.get(Emotion, idea.target_emotion_id) if idea.target_emotion_id is not None else None
    return (
        pillar.name if pillar else None,
        fmt.name if fmt else None,
        emotion.name if emotion else None,
    )


def _pillar_format_emotion_by_log(db: Session, log_ids: list[int]) -> dict[int, tuple[str | None, str | None, str | None]]:
    logs = db.query(PublishLog.id, PublishLog.ai_story_job_id).filter(PublishLog.id.in_(log_ids)).all()
    job_id_by_log = {row[0]: row[1] for row in logs}

    resolved_by_job: dict[int | None, tuple[str | None, str | None, str | None]] = {None: (None, None, None)}
    result: dict[int, tuple[str | None, str | None, str | None]] = {}
    for log_id, job_id in job_id_by_log.items():
        if job_id not in resolved_by_job:
            resolved_by_job[job_id] = _resolve_pillar_format_emotion(db, job_id)
        result[log_id] = resolved_by_job[job_id]
    return result


def get_performance_service(db: Session = Depends(get_db)) -> PerformanceService:
    return PerformanceService(db)


@router.get("/recommendations/content", response_model=list[RecommendationOut])
def content_recommendations(
    dimension: str | None = Query(None, description="Filter to one of: pillar, format, hook, emotion"),
    limit: int = Query(10, ge=1, le=50),
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    db: Session = Depends(get_db),
    service: PerformanceService = Depends(get_performance_service),
):
    """"What content should we generate next?" -- a combined, ranked list
    across pillar/format/hook/emotion (or just one, via `dimension`),
    each with its own transparent weight and reasons. Groups below
    min_sample_size are excluded outright (see recommendation_service's
    own module docstring) -- never recommended on too little data, and
    this endpoint never writes anything.
    """
    performances = service.all_performances()
    by_log = _pillar_format_emotion_by_log(db, [p.publish_log_id for p in performances])

    dimensions_to_run = (dimension,) if dimension in DIMENSIONS else DIMENSIONS

    all_recommendations = []
    for dim in dimensions_to_run:
        if dim == "pillar":
            key_fn = lambda p: by_log.get(p.publish_log_id, (None, None, None))[0]  # noqa: E731
        elif dim == "format":
            key_fn = lambda p: by_log.get(p.publish_log_id, (None, None, None))[1]  # noqa: E731
        elif dim == "emotion":
            key_fn = lambda p: by_log.get(p.publish_log_id, (None, None, None))[2]  # noqa: E731
        elif dim == "hook":
            key_fn = lambda p: p.hook_type  # noqa: E731
        else:
            continue

        stats = compute_group_stats(performances, key_fn, lambda k: k, dim, min_sample_size)
        trends = compute_trends(performances, key_fn, lambda k: k, dim, min_sample_size)
        trends_by_label = {t.label: t for t in trends}
        all_recommendations.extend(rank_recommendations(stats, trends_by_label))

    all_recommendations.sort(key=lambda r: r.weight, reverse=True)
    return all_recommendations[:limit]
