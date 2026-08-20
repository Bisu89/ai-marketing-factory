from fastapi import APIRouter, Depends

from app.api.deps import get_publish_log_service
from app.schemas.publish_log import (
    LinkPostIn,
    PublishLogCreateIn,
    PublishLogOut,
    PublishLogUpdateIn,
    publish_log_to_out,
)
from app.services.insights.publish_log_service import PublishLogService, latest_snapshot_for

router = APIRouter()


def _to_out(service: PublishLogService, log) -> PublishLogOut:
    views = interactions = None
    if log.post_id and log.page_id:
        snapshot = latest_snapshot_for(service.db, log.post_id, log.page_id)
        if snapshot is not None:
            views, interactions = snapshot.views, snapshot.interactions
    return publish_log_to_out(log, views=views, interactions=interactions)


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
        affiliate_link_id=payload.affiliate_link_id,
        published_at=payload.published_at,
        status=payload.status,
        notes=payload.notes,
    )
    return _to_out(service, log)


@router.get("/publish-logs", response_model=list[PublishLogOut])
def list_publish_logs(
    video_id: int | None = None,
    service: PublishLogService = Depends(get_publish_log_service),
):
    return [_to_out(service, log) for log in service.list_logs(video_id)]


@router.get("/publish-logs/{log_id}", response_model=PublishLogOut)
def get_publish_log(
    log_id: int,
    service: PublishLogService = Depends(get_publish_log_service),
):
    return _to_out(service, service.get(log_id))


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
        affiliate_link_id=payload.affiliate_link_id,
        status=payload.status,
        notes=payload.notes,
    )
    return _to_out(service, log)


@router.delete("/publish-logs/{log_id}", status_code=204)
def delete_publish_log(
    log_id: int,
    service: PublishLogService = Depends(get_publish_log_service),
):
    service.delete(log_id)


@router.post("/publish-logs/{log_id}/link-post", response_model=PublishLogOut)
def link_publish_log_to_post(
    log_id: int,
    payload: LinkPostIn,
    service: PublishLogService = Depends(get_publish_log_service),
):
    log = service.link_to_post(log_id, payload.post_id, payload.page_id)
    return _to_out(service, log)


@router.post("/publish-logs/{log_id}/unlink", response_model=PublishLogOut)
def unlink_publish_log(
    log_id: int,
    service: PublishLogService = Depends(get_publish_log_service),
):
    log = service.unlink(log_id)
    return _to_out(service, log)
