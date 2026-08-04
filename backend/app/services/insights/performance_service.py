from collections.abc import Callable
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from app.models.publish_log import PublishLog
from app.services.insights.publish_log_service import latest_snapshot_for


@dataclass
class LinkedPerformance:
    publish_log: PublishLog
    views: int
    interactions: int


@dataclass
class DimensionBreakdown:
    label: str
    post_count: int
    total_views: int
    avg_views: float
    total_interactions: int


class PerformanceService:
    """Aggregates real performance numbers (from linked InsightPostSnapshot
    rows) by the creative dimensions captured on PublishLog. Groups in
    Python rather than SQL -- matches the existing InsightService.get_by_post_type
    style, and the expected data volume (one creator's own published videos)
    doesn't warrant more than that.
    """

    def __init__(self, db: Session):
        self.db = db

    def _linked_performance(self) -> list[LinkedPerformance]:
        logs = (
            self.db.query(PublishLog)
            .options(selectinload(PublishLog.video))
            .filter(PublishLog.post_id.isnot(None), PublishLog.page_id.isnot(None))
            .all()
        )
        result: list[LinkedPerformance] = []
        for log in logs:
            snapshot = latest_snapshot_for(self.db, log.post_id, log.page_id)
            if snapshot is None:
                continue
            result.append(LinkedPerformance(publish_log=log, views=snapshot.views, interactions=snapshot.interactions))
        return result

    @staticmethod
    def _breakdown_by(items: list[LinkedPerformance], key_fn: Callable[[PublishLog], str | None]) -> list[DimensionBreakdown]:
        groups: dict[str, list[LinkedPerformance]] = defaultdict(list)
        for item in items:
            key = key_fn(item.publish_log) or "Không rõ"
            groups[key].append(item)

        breakdown = [
            DimensionBreakdown(
                label=label,
                post_count=len(group),
                total_views=sum(g.views for g in group),
                avg_views=round(sum(g.views for g in group) / len(group), 1),
                total_interactions=sum(g.interactions for g in group),
            )
            for label, group in groups.items()
        ]
        breakdown.sort(key=lambda b: b.total_views, reverse=True)
        return breakdown

    def get_overview(self) -> dict[str, list[DimensionBreakdown]]:
        items = self._linked_performance()
        return {
            "by_topic": self._breakdown_by(items, lambda log: log.video.category_name),
            "by_emotion": self._breakdown_by(items, lambda log: log.video.emotion_name),
            "by_hook_type": self._breakdown_by(items, lambda log: log.hook_type),
            "by_story_style": self._breakdown_by(items, lambda log: log.story_style),
        }

    def get_ranked(self, limit: int, ascending: bool) -> list[LinkedPerformance]:
        items = self._linked_performance()
        items.sort(key=lambda i: i.views, reverse=not ascending)
        return items[:limit]
