from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoPerformanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    publish_log_id: int
    video_id: int
    video_title: str
    platform: str
    page_name: str | None
    hook_type: str | None
    story_style: str | None
    linked: bool

    views: int | None
    interactions: int | None
    comments: int | None
    shares: int | None
    reactions: int | None
    saves: int | None
    real_followers: int | None

    engagement_rate: float | None
    follower_conversion_rate: float | None

    view_velocity_per_day: float | None
    view_velocity_note: str | None

    performance_score: float | None
    performance_score_note: str | None

    data_note: str | None


class DimensionPerformanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    sample_size: int
    linked_sample_size: int
    total_views: int | None
    avg_views: float | None
    avg_engagement_rate: float | None
    note: str | None


class PerformanceTimePointOut(BaseModel):
    upload_id: int
    uploaded_at: datetime
    filename: str
    total_views: int
    total_interactions: int
