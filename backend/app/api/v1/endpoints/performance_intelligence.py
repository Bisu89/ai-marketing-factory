"""Task 07 -- Performance Intelligence. Composition root: the one place
allowed to import app.services.insights (core) together with
app.modules.ai.story and app.modules.content_strategy (per
app/modules/README.md, core never points out and modules never import
each other) -- needed only for Top Pillars/Top Formats, which trace
PublishLog -> StoryJob (via PublishLog.ai_story_job_id) -> ContentIdea
(via StoryJob.content_idea_id, Task 04) -> ContentPillar/ContentFormat.
Every other endpoint here is a thin pass-through to
app.services.insights.performance_service.PerformanceService (Repository
[app/services/insights/publish_log_service.py's snapshot lookups] ->
Service [PerformanceService] -> API [this file], per this task's own
required layering) or to the pre-existing InsightService.get_trend() for
"performance over time" (reused, not duplicated).

Read-only throughout -- no endpoint here writes anything.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.publish_log import PublishLog
from app.modules.ai.story.models import StoryJob
from app.modules.content_strategy.models import ContentFormat, ContentIdea, ContentPillar
from app.schemas.insight import TrendPointOut
from app.schemas.performance import DimensionPerformanceOut, VideoPerformanceOut
from app.services.insights.performance_service import PerformanceService, VideoPerformance, group_performances_by
from app.services.insights.service import InsightService

router = APIRouter()


def _resolve_pillar_format(db: Session, ai_story_job_id: int | None) -> tuple[str | None, str | None]:
    """None, None whenever the chain is broken anywhere along the way --
    never guessed. Broken today for the vast majority of PublishLogs,
    since ai_story_job_id is only ever set by a caller that explicitly
    chose to (the frontend picker for it was removed, see
    docs/features/63-remove-ai-content-and-insights.md) and StoryJob.
    content_idea_id is only set when that Story was generated through
    Task 04's Content Idea bridge, not the plain manual /story-jobs.
    """
    if ai_story_job_id is None:
        return None, None
    job = db.get(StoryJob, ai_story_job_id)
    if job is None or job.content_idea_id is None:
        return None, None
    idea = db.get(ContentIdea, job.content_idea_id)
    if idea is None:
        return None, None
    pillar = db.get(ContentPillar, idea.pillar_id)
    fmt = db.get(ContentFormat, idea.format_id)
    return (pillar.name if pillar else None), (fmt.name if fmt else None)


def _pillar_format_by_log(db: Session, performances: list[VideoPerformance]) -> dict[int, tuple[str | None, str | None]]:
    """One query for every PublishLog's ai_story_job_id (not N), then one
    _resolve_pillar_format per distinct job id -- avoids an N+1 query
    pattern across a potentially long performance list.
    """
    log_ids = [p.publish_log_id for p in performances]
    logs = db.query(PublishLog.id, PublishLog.ai_story_job_id).filter(PublishLog.id.in_(log_ids)).all()
    job_id_by_log = {row[0]: row[1] for row in logs}

    resolved_by_job: dict[int | None, tuple[str | None, str | None]] = {None: (None, None)}
    result: dict[int, tuple[str | None, str | None]] = {}
    for log_id, job_id in job_id_by_log.items():
        if job_id not in resolved_by_job:
            resolved_by_job[job_id] = _resolve_pillar_format(db, job_id)
        result[log_id] = resolved_by_job[job_id]
    return result


def get_performance_service(db: Session = Depends(get_db)) -> PerformanceService:
    return PerformanceService(db)


def get_insight_service(db: Session = Depends(get_db)) -> InsightService:
    return InsightService(db)


# -- 1. Top videos -----------------------------------------------------


@router.get("/performance/videos", response_model=list[VideoPerformanceOut])
def top_videos(limit: int = 10, service: PerformanceService = Depends(get_performance_service)):
    return service.top_videos(limit)


# -- 2. Top hooks --------------------------------------------------------


@router.get("/performance/hooks", response_model=list[DimensionPerformanceOut])
def top_hooks(service: PerformanceService = Depends(get_performance_service)):
    return service.top_hooks()


# -- 3. Top story styles ---------------------------------------------------


@router.get("/performance/story-styles", response_model=list[DimensionPerformanceOut])
def top_story_styles(service: PerformanceService = Depends(get_performance_service)):
    return service.top_story_styles()


# -- 4/5. Top pillars / Top formats (needs the cross-module join above) ------


@router.get("/performance/pillars", response_model=list[DimensionPerformanceOut])
def top_pillars(db: Session = Depends(get_db), service: PerformanceService = Depends(get_performance_service)):
    performances = service.all_performances()
    by_log = _pillar_format_by_log(db, performances)
    return group_performances_by(performances, lambda p: by_log.get(p.publish_log_id, (None, None))[0], lambda k: k)


@router.get("/performance/formats", response_model=list[DimensionPerformanceOut])
def top_formats(db: Session = Depends(get_db), service: PerformanceService = Depends(get_performance_service)):
    performances = service.all_performances()
    by_log = _pillar_format_by_log(db, performances)
    return group_performances_by(performances, lambda p: by_log.get(p.publish_log_id, (None, None))[1], lambda k: k)


# -- 6. Performance by platform ---------------------------------------------


@router.get("/performance/platforms", response_model=list[DimensionPerformanceOut])
def by_platform(service: PerformanceService = Depends(get_performance_service)):
    return service.by_platform()


# -- 7. Performance over time (reuses the existing Insights trend --
#       aggregate, time-series by nature, already exactly this) ------------


@router.get("/performance/over-time", response_model=list[TrendPointOut])
def over_time(service: InsightService = Depends(get_insight_service)):
    return service.get_trend()
