from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.insight_post import InsightPostSnapshot
from app.models.publish_log import PublishLog
from app.models.video import Video


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def latest_snapshot_for(db: Session, post_id: str, page_id: str) -> InsightPostSnapshot | None:
    """The InsightPostSnapshot with these post_id/page_id from the most
    recent upload -- since a real-world post accumulates a growing-numbers
    snapshot on every re-upload, "the latest one" is the current truth.
    Ordered by id (autoincrement, assigned at insert time) rather than a
    join back to InsightUpload.uploaded_at -- equivalent in practice since
    rows are always inserted in upload order, and simpler. Restored for
    Task 07 (Performance Intelligence) -- see
    docs/features/72-performance-intelligence.md.
    """
    return (
        db.query(InsightPostSnapshot)
        .filter(InsightPostSnapshot.post_id == post_id, InsightPostSnapshot.page_id == page_id)
        .order_by(InsightPostSnapshot.id.desc())
        .first()
    )


def all_snapshots_for(db: Session, post_id: str, page_id: str) -> list[InsightPostSnapshot]:
    """Every snapshot on file for this post, oldest first -- unlike
    latest_snapshot_for (the current truth for a single-value read), this
    is what a *trend across uploads* (e.g. view velocity) needs: the growth
    between two real, dated snapshots, not a single point.
    """
    return (
        db.query(InsightPostSnapshot)
        .filter(InsightPostSnapshot.post_id == post_id, InsightPostSnapshot.page_id == page_id)
        .order_by(InsightPostSnapshot.id.asc())
        .all()
    )


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

    def link_to_post(self, log_id: int, post_id: str, page_id: str) -> PublishLog:
        """Restored for Task 07 -- without this, post_id/page_id can never
        be set on any PublishLog, and every performance metric that
        depends on a linked InsightPostSnapshot would be permanently null
        for every row, not just the ones genuinely never uploaded/linked.
        """
        log = self._get(log_id)
        snapshot = latest_snapshot_for(self.db, post_id, page_id)
        if snapshot is None:
            raise NotFoundError("Insight post", f"{post_id}/{page_id}")

        already_linked = (
            self.db.query(PublishLog)
            .filter(PublishLog.post_id == post_id, PublishLog.page_id == page_id, PublishLog.id != log_id)
            .first()
        )
        if already_linked is not None:
            raise ValidationError("Bài đăng này đã được gắn với một video khác.")

        log.post_id = post_id
        log.page_id = page_id
        self.db.commit()
        self.db.refresh(log)
        return log

    def unlink(self, log_id: int) -> PublishLog:
        log = self._get(log_id)
        log.post_id = None
        log.page_id = None
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_unlinked_posts(self) -> list[InsightPostSnapshot]:
        """Latest snapshot per (post_id, page_id) that has no PublishLog
        pointing at it yet.
        """
        linked = self.db.query(PublishLog.post_id, PublishLog.page_id).filter(PublishLog.post_id.isnot(None))
        linked_pairs = {(row[0], row[1]) for row in linked}

        latest_ids_subquery = self.db.query(func.max(InsightPostSnapshot.id)).group_by(
            InsightPostSnapshot.post_id, InsightPostSnapshot.page_id
        )
        candidates = (
            self.db.query(InsightPostSnapshot).filter(InsightPostSnapshot.id.in_(latest_ids_subquery)).all()
        )
        return [c for c in candidates if (c.post_id, c.page_id) not in linked_pairs]
