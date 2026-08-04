from fastapi import APIRouter, Depends

from app.api.deps import get_performance_service
from app.schemas.performance import PerformanceOverviewOut, breakdown_to_out
from app.schemas.publish_log import PublishLogOut, publish_log_to_out
from app.services.insights.performance_service import PerformanceService

router = APIRouter()


@router.get("/performance/overview", response_model=PerformanceOverviewOut)
def get_performance_overview(service: PerformanceService = Depends(get_performance_service)):
    overview = service.get_overview()
    return PerformanceOverviewOut(
        by_topic=[breakdown_to_out(b) for b in overview["by_topic"]],
        by_emotion=[breakdown_to_out(b) for b in overview["by_emotion"]],
        by_hook_type=[breakdown_to_out(b) for b in overview["by_hook_type"]],
        by_story_style=[breakdown_to_out(b) for b in overview["by_story_style"]],
    )


@router.get("/performance/winners", response_model=list[PublishLogOut])
def get_winners(limit: int = 10, service: PerformanceService = Depends(get_performance_service)):
    ranked = service.get_ranked(limit, ascending=False)
    return [publish_log_to_out(r.publish_log, views=r.views, interactions=r.interactions) for r in ranked]


@router.get("/performance/losers", response_model=list[PublishLogOut])
def get_losers(limit: int = 10, service: PerformanceService = Depends(get_performance_service)):
    ranked = service.get_ranked(limit, ascending=True)
    return [publish_log_to_out(r.publish_log, views=r.views, interactions=r.interactions) for r in ranked]
