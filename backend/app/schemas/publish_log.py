from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.publish_log import PUBLISH_LOG_STATUSES, PublishLog


class PublishLogCreateIn(BaseModel):
    video_id: int
    platform: str = "facebook"
    page_name: str | None = None
    hook_type: str | None = None
    story_style: str | None = None
    ai_story_job_id: int | None = None
    affiliate_product: str | None = None
    affiliate_clicks: int = 0
    affiliate_sales: int = 0
    affiliate_revenue: float = 0
    published_at: datetime | None = None
    status: str = "none"
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in PUBLISH_LOG_STATUSES:
            raise ValueError(f"Invalid status {value!r}, must be one of {PUBLISH_LOG_STATUSES}")
        return value


class PublishLogUpdateIn(BaseModel):
    page_name: str | None = None
    hook_type: str | None = None
    story_style: str | None = None
    affiliate_product: str | None = None
    affiliate_clicks: int | None = None
    affiliate_sales: int | None = None
    affiliate_revenue: float | None = None
    status: str | None = None
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in PUBLISH_LOG_STATUSES:
            raise ValueError(f"Invalid status {value!r}, must be one of {PUBLISH_LOG_STATUSES}")
        return value


class LinkPostIn(BaseModel):
    post_id: str
    page_id: str


class PublishLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    video_title: str
    video_topic: str | None
    video_emotion: str | None
    platform: str
    page_name: str | None
    hook_type: str | None
    story_style: str | None
    ai_story_job_id: int | None
    affiliate_product: str | None
    affiliate_clicks: int
    affiliate_sales: int
    affiliate_revenue: float
    published_at: datetime
    status: str
    post_id: str | None
    page_id: str | None
    notes: str | None
    created_at: datetime
    # Restored for Task 07 -- populated only when linked to a real
    # InsightPostSnapshot, resolved live by the service layer, never
    # stored here (see docs/features/72-performance-intelligence.md).
    views: int | None = None
    interactions: int | None = None


def publish_log_to_out(log: PublishLog, views: int | None = None, interactions: int | None = None) -> PublishLogOut:
    return PublishLogOut(
        id=log.id,
        video_id=log.video_id,
        video_title=log.video.title,
        video_topic=log.video.category_name,
        video_emotion=log.video.emotion_name,
        platform=log.platform,
        page_name=log.page_name,
        hook_type=log.hook_type,
        story_style=log.story_style,
        ai_story_job_id=log.ai_story_job_id,
        affiliate_product=log.affiliate_product,
        affiliate_clicks=log.affiliate_clicks,
        affiliate_sales=log.affiliate_sales,
        affiliate_revenue=log.affiliate_revenue,
        published_at=log.published_at,
        status=log.status,
        post_id=log.post_id,
        page_id=log.page_id,
        notes=log.notes,
        created_at=log.created_at,
        views=views,
        interactions=interactions,
    )
