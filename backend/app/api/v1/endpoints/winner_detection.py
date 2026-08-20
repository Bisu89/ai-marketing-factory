"""Task 08 -- Content Winner Detection. Composition root, same shape as
Task 07's performance_intelligence.py (the one place allowed to import
app.services.insights together with app.modules.ai.story and
app.modules.content_strategy) -- reused directly for pillar/format
resolution (_pillar_format_by_log) rather than duplicated, same
"composition roots may import each other's small helpers" precedent
app/api/v1/endpoints/content_batch_generate.py already uses for
content_idea_generation.py's _load_idea_context.

Every endpoint here is read-only and delegates to
app.services.insights.winner_detection_service, which itself only
aggregates PerformanceService.all_performances() (Task 07) -- no metric
is computed twice.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.endpoints.performance_intelligence import _pillar_format_by_log, get_performance_service
from app.db.session import get_db
from app.schemas.winner_detection import TrendGroupStatsOut, WinnerGroupStatsOut
from app.services.insights.performance_service import PerformanceService
from app.services.insights.winner_detection_service import (
    DEFAULT_MIN_SAMPLE_SIZE,
    compute_group_stats,
    compute_trends,
    key_by_duration,
)

router = APIRouter()


# -- Core-only dimensions (hook / story style / platform / duration) -------


@router.get("/winners/hooks", response_model=list[WinnerGroupStatsOut])
def winner_hooks(
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    service: PerformanceService = Depends(get_performance_service),
):
    return compute_group_stats(service.all_performances(), lambda p: p.hook_type, lambda k: k, "hook", min_sample_size)


@router.get("/winners/story-styles", response_model=list[WinnerGroupStatsOut])
def winner_story_styles(
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    service: PerformanceService = Depends(get_performance_service),
):
    return compute_group_stats(
        service.all_performances(), lambda p: p.story_style, lambda k: k, "story_style", min_sample_size
    )


@router.get("/winners/platforms", response_model=list[WinnerGroupStatsOut])
def winner_platforms(
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    service: PerformanceService = Depends(get_performance_service),
):
    return compute_group_stats(service.all_performances(), lambda p: p.platform, lambda k: k, "platform", min_sample_size)


@router.get("/winners/duration", response_model=list[WinnerGroupStatsOut])
def winner_duration(
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    service: PerformanceService = Depends(get_performance_service),
):
    """Bucketed via app.services.library.repository.DURATION_BUCKETS (the
    same buckets the Library page's own duration filter already uses).
    Videos with no known duration at all (neither the linked snapshot nor
    Video.duration_sec has it) are excluded from every bucket, same "don't
    guess" handling as pillar/format having no resolvable value.
    """
    return compute_group_stats(service.all_performances(), key_by_duration, lambda k: k, "duration", min_sample_size)


# -- Pillar / Format (needs the ai.story + content_strategy join) ------------


@router.get("/winners/pillars", response_model=list[WinnerGroupStatsOut])
def winner_pillars(
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    db: Session = Depends(get_db),
    service: PerformanceService = Depends(get_performance_service),
):
    performances = service.all_performances()
    by_log = _pillar_format_by_log(db, performances)
    return compute_group_stats(
        performances, lambda p: by_log.get(p.publish_log_id, (None, None))[0], lambda k: k, "pillar", min_sample_size
    )


@router.get("/winners/formats", response_model=list[WinnerGroupStatsOut])
def winner_formats(
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    db: Session = Depends(get_db),
    service: PerformanceService = Depends(get_performance_service),
):
    performances = service.all_performances()
    by_log = _pillar_format_by_log(db, performances)
    return compute_group_stats(
        performances, lambda p: by_log.get(p.publish_log_id, (None, None))[1], lambda k: k, "format", min_sample_size
    )


# -- Rising / Underperforming Formats ----------------------------------------


@router.get("/winners/formats/rising", response_model=list[TrendGroupStatsOut])
def rising_formats(
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    db: Session = Depends(get_db),
    service: PerformanceService = Depends(get_performance_service),
):
    performances = service.all_performances()
    by_log = _pillar_format_by_log(db, performances)
    trends = compute_trends(
        performances, lambda p: by_log.get(p.publish_log_id, (None, None))[1], lambda k: k, "format", min_sample_size
    )
    return [t for t in trends if t.trend == "rising"]


@router.get("/winners/formats/underperforming", response_model=list[WinnerGroupStatsOut])
def underperforming_formats(
    min_sample_size: int = Query(DEFAULT_MIN_SAMPLE_SIZE, ge=1),
    db: Session = Depends(get_db),
    service: PerformanceService = Depends(get_performance_service),
):
    """Unlike Rising (a time-trend comparison), "underperforming" is an
    absolute-standing comparison: formats that meet the minimum sample
    size (so this never singles out a format on 1-2 videos) whose
    performance_score sits below the average across every format that
    also meets the minimum -- the bottom tier of a real, apples-to-apples
    comparison, not a fabricated ranking of formats with too little data
    to judge either way.
    """
    performances = service.all_performances()
    by_log = _pillar_format_by_log(db, performances)
    stats = compute_group_stats(
        performances, lambda p: by_log.get(p.publish_log_id, (None, None))[1], lambda k: k, "format", min_sample_size
    )
    eligible = [s for s in stats if s.meets_minimum_sample and s.performance_score is not None]
    if len(eligible) < 2:
        return []
    overall_avg = sum(s.performance_score for s in eligible) / len(eligible)
    return [s for s in eligible if s.performance_score < overall_avg]
