from datetime import datetime

from pydantic import BaseModel


class InsightUploadOut(BaseModel):
    id: int
    filename: str
    row_count: int
    uploaded_at: datetime
    skipped_rows: int = 0


class InsightSummaryOut(BaseModel):
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


class InsightPostOut(BaseModel):
    post_id: str
    title: str
    post_type: str | None
    permalink: str | None
    posted_at: datetime | None
    duration_sec: float | None
    views: int
    viewers: int
    interactions: int
    comments: int
    shares: int
    saves: int
    reactions: int
    retention_pct: float | None


class PostTypeBreakdownOut(BaseModel):
    post_type: str
    post_count: int
    total_views: int
    avg_views: float
    avg_retention_pct: float | None


class TrendPointOut(BaseModel):
    upload_id: int
    uploaded_at: datetime
    filename: str
    total_views: int
    total_interactions: int
