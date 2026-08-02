from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.deps import get_insight_service
from app.schemas.insight import (
    InsightPostOut,
    InsightSummaryOut,
    InsightUploadOut,
    PostTypeBreakdownOut,
    TrendPointOut,
)
from app.services.insights.csv_parser import InsightCsvError, parse_insight_csv
from app.services.insights.service import InsightService

router = APIRouter()


@router.post("/insights/upload", response_model=InsightUploadOut, status_code=201)
async def upload_insight_csv(
    file: UploadFile,
    service: InsightService = Depends(get_insight_service),
):
    raw = await file.read()
    try:
        rows, skipped = parse_insight_csv(raw)
    except InsightCsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(status_code=400, detail="File không có dòng dữ liệu hợp lệ nào.")

    upload = service.save_upload(file.filename or "upload.csv", rows)
    return InsightUploadOut(
        id=upload.id,
        filename=upload.filename,
        row_count=upload.row_count,
        uploaded_at=upload.uploaded_at,
        skipped_rows=skipped,
    )


@router.get("/insights/uploads", response_model=list[InsightUploadOut])
def list_uploads(service: InsightService = Depends(get_insight_service)):
    return [
        InsightUploadOut(id=u.id, filename=u.filename, row_count=u.row_count, uploaded_at=u.uploaded_at)
        for u in service.list_uploads()
    ]


@router.get("/insights/summary", response_model=InsightSummaryOut)
def get_summary(upload_id: int | None = None, service: InsightService = Depends(get_insight_service)):
    summary = service.get_summary(upload_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Chưa có dữ liệu nào được upload.")
    return summary


@router.get("/insights/posts", response_model=list[InsightPostOut])
def get_top_posts(
    upload_id: int | None = None,
    sort: str = "views",
    limit: int = 20,
    service: InsightService = Depends(get_insight_service),
):
    return [
        InsightPostOut(
            post_id=post.post_id,
            title=post.title,
            post_type=post.post_type,
            permalink=post.permalink,
            posted_at=post.posted_at,
            duration_sec=post.duration_sec,
            views=post.views,
            viewers=post.viewers,
            interactions=post.interactions,
            comments=post.comments,
            shares=post.shares,
            saves=post.saves,
            reactions=post.reactions,
            retention_pct=retention_pct,
        )
        for post, retention_pct in service.get_top_posts(upload_id, sort, limit)
    ]


@router.get("/insights/by-post-type", response_model=list[PostTypeBreakdownOut])
def get_by_post_type(upload_id: int | None = None, service: InsightService = Depends(get_insight_service)):
    return service.get_by_post_type(upload_id)


@router.get("/insights/trend", response_model=list[TrendPointOut])
def get_trend(service: InsightService = Depends(get_insight_service)):
    return service.get_trend()
