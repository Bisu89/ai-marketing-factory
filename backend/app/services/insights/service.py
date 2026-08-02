from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.insight_post import InsightPostSnapshot
from app.models.insight_upload import InsightUpload

_SORTABLE_FIELDS = {"views": InsightPostSnapshot.views, "interactions": InsightPostSnapshot.interactions}


def _retention_pct(post: InsightPostSnapshot) -> float | None:
    if not post.duration_sec:
        return None
    return round(post.avg_seconds_viewed / post.duration_sec * 100, 1)


@dataclass
class PostSummary:
    total_posts: int
    total_views: int
    total_viewers: int
    total_interactions: int
    total_comments: int
    total_shares: int
    total_saves: int
    total_reactions: int
    total_impressions: int
    avg_retention_pct: float | None


@dataclass
class PostTypeBreakdown:
    post_type: str
    post_count: int
    total_views: int
    avg_views: float
    avg_retention_pct: float | None


@dataclass
class TrendPoint:
    upload_id: int
    uploaded_at: datetime
    filename: str
    total_views: int
    total_interactions: int


class InsightService:
    def __init__(self, db: Session):
        self._db = db

    def save_upload(self, filename: str, rows: list[dict]) -> InsightUpload:
        upload = InsightUpload(filename=filename, row_count=len(rows))
        self._db.add(upload)
        self._db.flush()

        for row in rows:
            self._db.add(InsightPostSnapshot(upload_id=upload.id, **row))

        self._db.commit()
        self._db.refresh(upload)
        return upload

    def list_uploads(self) -> list[InsightUpload]:
        return self._db.query(InsightUpload).order_by(InsightUpload.uploaded_at.desc()).all()

    def _resolve_upload_id(self, upload_id: int | None) -> int | None:
        if upload_id is not None:
            return upload_id
        latest = self._db.query(InsightUpload).order_by(InsightUpload.uploaded_at.desc()).first()
        return latest.id if latest else None

    def get_summary(self, upload_id: int | None) -> PostSummary | None:
        resolved_id = self._resolve_upload_id(upload_id)
        if resolved_id is None:
            return None

        posts = self._db.query(InsightPostSnapshot).filter(InsightPostSnapshot.upload_id == resolved_id).all()
        if not posts:
            return PostSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, None)

        retentions = [r for r in (_retention_pct(p) for p in posts) if r is not None]
        return PostSummary(
            total_posts=len(posts),
            total_views=sum(p.views for p in posts),
            total_viewers=sum(p.viewers for p in posts),
            total_interactions=sum(p.interactions for p in posts),
            total_comments=sum(p.comments for p in posts),
            total_shares=sum(p.shares for p in posts),
            total_saves=sum(p.saves for p in posts),
            total_reactions=sum(p.reactions for p in posts),
            total_impressions=sum(p.impressions for p in posts),
            avg_retention_pct=round(sum(retentions) / len(retentions), 1) if retentions else None,
        )

    def get_top_posts(
        self, upload_id: int | None, sort: str = "views", limit: int = 20
    ) -> list[tuple[InsightPostSnapshot, float | None]]:
        resolved_id = self._resolve_upload_id(upload_id)
        if resolved_id is None:
            return []

        sort_col = _SORTABLE_FIELDS.get(sort, InsightPostSnapshot.views)
        posts = (
            self._db.query(InsightPostSnapshot)
            .filter(InsightPostSnapshot.upload_id == resolved_id)
            .order_by(sort_col.desc())
            .limit(limit)
            .all()
        )
        return [(p, _retention_pct(p)) for p in posts]

    def get_by_post_type(self, upload_id: int | None) -> list[PostTypeBreakdown]:
        resolved_id = self._resolve_upload_id(upload_id)
        if resolved_id is None:
            return []

        posts = self._db.query(InsightPostSnapshot).filter(InsightPostSnapshot.upload_id == resolved_id).all()
        by_type: dict[str, list[InsightPostSnapshot]] = {}
        for post in posts:
            by_type.setdefault(post.post_type or "Không rõ", []).append(post)

        breakdown = []
        for post_type, group in by_type.items():
            retentions = [r for r in (_retention_pct(p) for p in group) if r is not None]
            total_views = sum(p.views for p in group)
            breakdown.append(
                PostTypeBreakdown(
                    post_type=post_type,
                    post_count=len(group),
                    total_views=total_views,
                    avg_views=round(total_views / len(group), 1),
                    avg_retention_pct=round(sum(retentions) / len(retentions), 1) if retentions else None,
                )
            )
        breakdown.sort(key=lambda b: b.total_views, reverse=True)
        return breakdown

    def get_trend(self) -> list[TrendPoint]:
        rows = (
            self._db.query(
                InsightUpload.id,
                InsightUpload.uploaded_at,
                InsightUpload.filename,
                func.coalesce(func.sum(InsightPostSnapshot.views), 0),
                func.coalesce(func.sum(InsightPostSnapshot.interactions), 0),
            )
            .outerjoin(InsightPostSnapshot, InsightPostSnapshot.upload_id == InsightUpload.id)
            .group_by(InsightUpload.id)
            .order_by(InsightUpload.uploaded_at.asc())
            .all()
        )
        return [
            TrendPoint(upload_id=r[0], uploaded_at=r[1], filename=r[2], total_views=r[3], total_interactions=r[4])
            for r in rows
        ]
