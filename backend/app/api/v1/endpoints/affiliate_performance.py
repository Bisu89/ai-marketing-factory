"""Task 12 -- Affiliate Engine KPIs. Composition root: the one place
allowed to import app.modules.affiliate together with the core
PublishLog and app.services.insights (for real view counts, needed for
"revenue per 1,000 views"), per app/modules/README.md.

Every number here is either a real, atomic count (AffiliateLink.click_count)
or a REUSE of PublishLog's own existing, manually-entered affiliate_sales/
affiliate_revenue (never a duplicate) -- GMV is the one genuinely derived
number (sales x product.price), and only computed for rows where both are
actually known; rows that can't contribute are counted and disclosed, not
silently dropped. Read-only throughout.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.publish_log import PublishLog
from app.modules.affiliate.models import AffiliateLink, AffiliateProduct
from app.services.insights.publish_log_service import latest_snapshot_for

router = APIRouter()


class AffiliateKPIOut(BaseModel):
    total_clicks: int
    real_tracked_clicks: int
    manual_clicks: int
    total_orders: int
    total_commission_usd: float
    total_gmv_usd: float
    gmv_excluded_orders: int  # orders that couldn't contribute to GMV (no linked product price)
    revenue_per_1000_views_usd: float | None
    revenue_per_1000_views_note: str | None
    revenue_per_video_usd: float | None
    videos_with_commercial_activity: int


@router.get("/affiliate/kpi", response_model=AffiliateKPIOut)
def affiliate_kpi(db: Session = Depends(get_db)):
    logs = db.query(PublishLog).options(selectinload(PublishLog.video)).all()

    link_by_id = {link.id: link for link in db.query(AffiliateLink).options(selectinload(AffiliateLink.product)).all()}

    real_tracked_clicks = sum(
        link.click_count for link in link_by_id.values() if any(log.affiliate_link_id == link.id for log in logs)
    )
    manual_clicks = sum(log.affiliate_clicks for log in logs if log.affiliate_link_id is None)

    total_orders = sum(log.affiliate_sales for log in logs)
    total_commission = sum(log.affiliate_revenue for log in logs)

    total_gmv = 0.0
    gmv_excluded = 0
    for log in logs:
        if log.affiliate_sales <= 0:
            continue
        link = link_by_id.get(log.affiliate_link_id) if log.affiliate_link_id else None
        product: AffiliateProduct | None = link.product if link else None
        if product is not None and product.price is not None:
            total_gmv += log.affiliate_sales * product.price
        else:
            gmv_excluded += 1

    revenue_logs = [log for log in logs if log.affiliate_revenue > 0]
    total_views_with_revenue = 0
    views_known_for_all = True
    for log in revenue_logs:
        if not (log.post_id and log.page_id):
            views_known_for_all = False
            continue
        snapshot = latest_snapshot_for(db, log.post_id, log.page_id)
        if snapshot is None:
            views_known_for_all = False
            continue
        total_views_with_revenue += snapshot.views

    if not revenue_logs:
        revenue_per_1000_views = None
        revenue_per_1000_views_note = "Chưa có publish nào ghi nhận affiliate_revenue."
    elif total_views_with_revenue <= 0:
        revenue_per_1000_views = None
        revenue_per_1000_views_note = "Các publish có affiliate_revenue chưa gắn dữ liệu Insights (views) thật."
    else:
        revenue_per_1000_views = round(sum(log.affiliate_revenue for log in revenue_logs) / (total_views_with_revenue / 1000), 4)
        revenue_per_1000_views_note = None if views_known_for_all else "Một số publish có revenue chưa có views thật -- tỷ lệ chỉ tính trên phần đã biết."

    commercial_video_ids = {log.video_id for log in logs if log.affiliate_link_id is not None or log.affiliate_revenue > 0}
    revenue_per_video = round(total_commission / len(commercial_video_ids), 2) if commercial_video_ids else None

    return AffiliateKPIOut(
        total_clicks=real_tracked_clicks + manual_clicks,
        real_tracked_clicks=real_tracked_clicks,
        manual_clicks=manual_clicks,
        total_orders=total_orders,
        total_commission_usd=round(total_commission, 2),
        total_gmv_usd=round(total_gmv, 2),
        gmv_excluded_orders=gmv_excluded,
        revenue_per_1000_views_usd=revenue_per_1000_views,
        revenue_per_1000_views_note=revenue_per_1000_views_note,
        revenue_per_video_usd=revenue_per_video,
        videos_with_commercial_activity=len(commercial_video_ids),
    )
