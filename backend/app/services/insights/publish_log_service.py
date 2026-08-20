from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError
from app.models.publish_log import PublishLog
from app.models.video import Video


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PublishLogService:
    def __init__(self, db: Session):
        self.db = db

    def _get(self, log_id: int) -> PublishLog:
        log = (
            self.db.query(PublishLog)
            .options(selectinload(PublishLog.video))
            .filter(PublishLog.id == log_id)
            .first()
        )
        if log is None:
            raise NotFoundError("Publish log", log_id)
        return log

    def get(self, log_id: int) -> PublishLog:
        return self._get(log_id)

    def create(
        self,
        video_id: int,
        platform: str,
        page_name: str | None,
        hook_type: str | None,
        story_style: str | None,
        ai_story_job_id: int | None,
        affiliate_product: str | None,
        affiliate_clicks: int,
        affiliate_sales: int,
        affiliate_revenue: float,
        published_at: datetime | None,
        status: str,
        notes: str | None,
    ) -> PublishLog:
        if self.db.get(Video, video_id) is None:
            raise NotFoundError("Video", video_id)

        log = PublishLog(
            video_id=video_id,
            platform=platform,
            page_name=page_name,
            hook_type=hook_type,
            story_style=story_style,
            ai_story_job_id=ai_story_job_id,
            affiliate_product=affiliate_product,
            affiliate_clicks=affiliate_clicks,
            affiliate_sales=affiliate_sales,
            affiliate_revenue=affiliate_revenue,
            published_at=published_at or _utcnow(),
            status=status,
            notes=notes,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_logs(self, video_id: int | None = None) -> list[PublishLog]:
        query = self.db.query(PublishLog).options(selectinload(PublishLog.video))
        if video_id is not None:
            query = query.filter(PublishLog.video_id == video_id)
        return query.order_by(PublishLog.published_at.desc()).all()

    def update(
        self,
        log_id: int,
        page_name: str | None,
        hook_type: str | None,
        story_style: str | None,
        affiliate_product: str | None,
        affiliate_clicks: int | None,
        affiliate_sales: int | None,
        affiliate_revenue: float | None,
        status: str | None,
        notes: str | None,
    ) -> PublishLog:
        log = self._get(log_id)
        if page_name is not None:
            log.page_name = page_name
        if hook_type is not None:
            log.hook_type = hook_type
        if story_style is not None:
            log.story_style = story_style
        if affiliate_product is not None:
            log.affiliate_product = affiliate_product
        if affiliate_clicks is not None:
            log.affiliate_clicks = affiliate_clicks
        if affiliate_sales is not None:
            log.affiliate_sales = affiliate_sales
        if affiliate_revenue is not None:
            log.affiliate_revenue = affiliate_revenue
        if status is not None:
            log.status = status
        if notes is not None:
            log.notes = notes
        self.db.commit()
        self.db.refresh(log)
        return log

    def delete(self, log_id: int) -> None:
        log = self._get(log_id)
        self.db.delete(log)
        self.db.commit()
