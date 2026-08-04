from pydantic import BaseModel

from app.services.insights.performance_service import DimensionBreakdown


class DimensionBreakdownOut(BaseModel):
    label: str
    post_count: int
    total_views: int
    avg_views: float
    total_interactions: int


def breakdown_to_out(breakdown: DimensionBreakdown) -> DimensionBreakdownOut:
    return DimensionBreakdownOut(
        label=breakdown.label,
        post_count=breakdown.post_count,
        total_views=breakdown.total_views,
        avg_views=breakdown.avg_views,
        total_interactions=breakdown.total_interactions,
    )


class PerformanceOverviewOut(BaseModel):
    by_topic: list[DimensionBreakdownOut]
    by_emotion: list[DimensionBreakdownOut]
    by_hook_type: list[DimensionBreakdownOut]
    by_story_style: list[DimensionBreakdownOut]
