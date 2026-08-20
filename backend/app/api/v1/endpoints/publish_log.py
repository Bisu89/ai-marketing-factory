from fastapi import APIRouter, Depends

from app.api.deps import get_publish_log_service
from app.schemas.publish_log import (
    PublishLogCreateIn,
    PublishLogOut,
    PublishLogUpdateIn,
    publish_log_to_out,
)
from app.services.insights.publish_log_service import PublishLogService

router = APIRouter()


@router.post("/publish-logs", response_model=PublishLogOut, status_code=201)
def create_publish_log(
    payload: PublishLogCreateIn,
    service: PublishLogService = Depends(get_publish_log_service),
):
    log = service.create(
        video_id=payload.video_id,
        platform=payload.platform,
        page_name=payload.page_name,
        hook_type=payload.hook_type,
        story_style=payload.story_style,
        ai_story_job_id=payload.ai_story_job_id,
        affiliate_product=payload.affiliate_product,
        affiliate_clicks=payload.affiliate_clicks,
        affiliate_sales=payload.affiliate_sales,
        affiliate_revenue=payload.affiliate_revenue,
        published_at=payload.published_at,
        status=payload.status,
        notes=payload.notes,
    )
    return publish_log_to_out(log)


@router.get("/publish-logs", response_model=list[PublishLogOut])
def list_publish_logs(
    video_id: int | None = None,
    service: PublishLogService = Depends(get_publish_log_service),
):
    return [publish_log_to_out(log) for log in service.list_logs(video_id)]


@router.get("/publish-logs/{log_id}", response_model=PublishLogOut)
def get_publish_log(
    log_id: int,
    service: PublishLogService = Depends(get_publish_log_service),
):
    return publish_log_to_out(service.get(log_id))


@router.put("/publish-logs/{log_id}", response_model=PublishLogOut)
def update_publish_log(
    log_id: int,
    payload: PublishLogUpdateIn,
    service: PublishLogService = Depends(get_publish_log_service),
):
    log = service.update(
        log_id,
        page_name=payload.page_name,
        hook_type=payload.hook_type,
        story_style=payload.story_style,
        affiliate_product=payload.affiliate_product,
        affiliate_clicks=payload.affiliate_clicks,
        affiliate_sales=payload.affiliate_sales,
        affiliate_revenue=payload.affiliate_revenue,
        status=payload.status,
        notes=payload.notes,
    )
    return publish_log_to_out(log)


@router.delete("/publish-logs/{log_id}", status_code=204)
def delete_publish_log(
    log_id: int,
    service: PublishLogService = Depends(get_publish_log_service),
):
    service.delete(log_id)
