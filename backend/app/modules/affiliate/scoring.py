"""Product Score -- deterministic, hand-tunable, transparent (same
convention as Task 08 winner_detection_service.py's performance_score and
Task 09 recommendation_service.py's weight formula): every component is
computed from data already real in this app (the catalog itself, or real
PublishLog.affiliate_sales figures the user logged) -- never a fabricated
market number. A component with no supporting data is EXCLUDED outright
(not scored as 0) and the remaining weights renormalize across whichever
components ARE available -- same "insufficient data -> excluded, never
guessed" convention used throughout this app.

"return risk" (explicitly named in this task's own spec) has no data
source anywhere in this app -- always excluded; the slot exists in
ScoreBreakdown in case that ever changes, never fabricated meanwhile.

"audience fit"/"story integration" (also in this task's spec) are NOT
part of this static, per-product score -- they are inherently
story-dependent (they change per piece of content), so they live in
matching.py's own contextual match_products(), combined with this static
score at recommendation time, mirroring Task 09's own
"static performance_score x contextual sample_confidence/recency" split.
"""

from dataclasses import dataclass

COMMISSION_WEIGHT = 0.35
PRICE_WEIGHT = 0.15
DEMAND_WEIGHT = 0.25
REVIEW_WEIGHT = 0.25
# RETURN_RISK_WEIGHT intentionally omitted -- no data source exists; see
# module docstring. Not listed here so it can never silently participate
# in renormalization.


@dataclass
class ScoreBreakdown:
    commission_component: float | None
    price_component: float | None
    demand_component: float | None
    review_component: float | None
    return_risk_component: float | None  # always None today -- see module docstring
    notes: list[str]


def _price_component(price: float | None, peer_prices: list[float]) -> tuple[float | None, str | None]:
    if price is None or price <= 0:
        return None, "Chưa có giá sản phẩm -- không tính được mức độ cạnh tranh về giá."
    if not peer_prices:
        return None, "Không có sản phẩm nào khác cùng category để so sánh giá."
    avg_peer_price = sum(peer_prices) / len(peer_prices)
    if avg_peer_price <= 0:
        return None, "Giá trung bình của các sản phẩm cùng category không hợp lệ."
    component = min(1.0, avg_peer_price / price)
    return component, f"Giá {price:,.0f} so với trung bình category {avg_peer_price:,.0f}."


def _demand_component(total_sales: int, max_total_sales_in_catalog: int) -> tuple[float | None, str | None]:
    if max_total_sales_in_catalog <= 0:
        return None, "Chưa có sản phẩm nào trong catalog có dữ liệu bán hàng thực tế (affiliate_sales) để làm mốc so sánh."
    component = min(1.0, total_sales / max_total_sales_in_catalog)
    if total_sales == 0:
        return 0.0, "Chưa ghi nhận đơn hàng thực tế nào cho sản phẩm này (so với mốc cao nhất trong catalog)."
    return component, f"{total_sales} đơn hàng thực tế đã ghi nhận (so với mốc cao nhất {max_total_sales_in_catalog} trong catalog)."


def _review_component(rating: float | None) -> tuple[float | None, str | None]:
    if rating is None:
        return None, "Chưa có rating -- bỏ qua thành phần chất lượng đánh giá."
    return max(0.0, min(1.0, rating / 5.0)), f"Rating {rating:.1f}/5."


def compute_product_score(
    *, commission_rate: float | None, price: float | None, peer_prices: list[float], total_sales: int, max_total_sales_in_catalog: int, rating: float | None
) -> tuple[float | None, ScoreBreakdown]:
    notes: list[str] = []

    commission_component = None
    if commission_rate is not None and commission_rate > 0:
        commission_component = max(0.0, min(1.0, commission_rate))
        notes.append(f"Commission rate {commission_rate * 100:.1f}%.")
    else:
        notes.append("Chưa có commission_rate -- bỏ qua thành phần hoa hồng.")

    price_component, price_note = _price_component(price, peer_prices)
    if price_note:
        notes.append(price_note)

    demand_component, demand_note = _demand_component(total_sales, max_total_sales_in_catalog)
    if demand_note:
        notes.append(demand_note)

    review_component, review_note = _review_component(rating)
    if review_note:
        notes.append(review_note)

    notes.append("Return risk: không có nguồn dữ liệu nào trong app này -- luôn bỏ qua.")

    weighted = [
        (COMMISSION_WEIGHT, commission_component),
        (PRICE_WEIGHT, price_component),
        (DEMAND_WEIGHT, demand_component),
        (REVIEW_WEIGHT, review_component),
    ]
    available = [(w, c) for w, c in weighted if c is not None]
    breakdown = ScoreBreakdown(
        commission_component=commission_component,
        price_component=price_component,
        demand_component=demand_component,
        review_component=review_component,
        return_risk_component=None,
        notes=notes,
    )

    if not available:
        return None, breakdown

    total_weight = sum(w for w, _ in available)
    score = sum(w * c for w, c in available) / total_weight * 100
    return round(score, 2), breakdown
