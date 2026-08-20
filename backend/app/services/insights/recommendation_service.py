"""Task 09 -- AI Content Learning Loop: a transparent, explainable scoring
layer on top of Task 08's WinnerGroupStats/TrendGroupStats -- explicitly
NOT machine learning (per this task's own "do not introduce ML
frameworks" instruction). Every number here is either already computed by
Task 08 or a small, documented, hand-tunable multiplier -- no model
training, no black box.

    weight = historical_performance x sample_confidence x recency_factor

matches this task's own example formula exactly. Each factor:

- historical_performance: Task 08's own performance_score (already a
  platform-normalized, non-raw-views score), rescaled to 0-1.
- sample_confidence: Task 08's own confidence tier (insufficient/low/
  medium/high), mapped to a 0-1 multiplier -- a group with insufficient
  samples gets exactly 0 and is excluded outright (this task inherits
  Task 08's "never call something a winner on 1-2 videos" rule; a
  recommendation is a stronger claim than a winner label, so the same
  floor applies at least as strictly).
- recency_factor: Task 08's own trend classification (rising/stable/
  underperforming/insufficient_data), mapped to a small boost/penalty
  around 1.0.

Every Recommendation carries its own reasons: list[str] built directly
from these numbers -- never a generic "AI recommends this," always
"why," per this task's own "each recommendation must include a short
explanation" and "do not silently manipulate generation" instructions.
"""

from dataclasses import dataclass

from app.services.insights.winner_detection_service import TrendGroupStats, WinnerGroupStats

# Tunable in one place, same "documented, hand-tunable weighting" shape
# Task 07/08's own performance_score/group score already use.
SAMPLE_CONFIDENCE_FACTORS = {
    "insufficient": 0.0,
    "low": 0.5,
    "medium": 0.75,
    "high": 1.0,
}

RECENCY_FACTORS = {
    "rising": 1.2,
    "stable": 1.0,
    "underperforming": 0.7,
    "insufficient_data": 0.85,  # mild caution, not a penalty -- we simply don't know yet
}

# performance_score (Task 08) is nominally 0-100 (60% views component capped
# at 3x platform average + 40% engagement rate*100) but isn't hard-capped at
# exactly 100 in every edge case -- clip when rescaling to 0-1 so weight
# never exceeds what the formula's own factors (max 1.0 x 1.0 x 1.2) allow.
_MAX_PERFORMANCE_SCORE = 100.0


@dataclass
class Recommendation:
    dimension: str  # "pillar" | "format" | "hook" | "emotion"
    label: str

    weight: float
    historical_performance: float  # 0-1
    sample_confidence: float  # 0-1
    recency_factor: float  # 0.7-1.2

    confidence_tier: str
    trend: str
    sample_size: int
    linked_sample_size: int

    reasons: list[str]


def _performance_reason(historical_performance: float, performance_score: float) -> str:
    if historical_performance >= 0.6:
        return f"Hiệu suất lịch sử mạnh (điểm hiệu suất {performance_score:.1f}/100)."
    if historical_performance >= 0.3:
        return f"Hiệu suất lịch sử ở mức khá (điểm hiệu suất {performance_score:.1f}/100)."
    return f"Hiệu suất lịch sử còn thấp (điểm hiệu suất {performance_score:.1f}/100)."


_CONFIDENCE_LABELS = {"low": "thấp", "medium": "trung bình", "high": "cao"}


def _sample_reason(linked_sample_size: int, confidence_tier: str) -> str:
    label = _CONFIDENCE_LABELS.get(confidence_tier, confidence_tier)
    return f"Đủ mẫu để đánh giá: {linked_sample_size} video, độ tin cậy {label}."


def _recency_reason(trend: str, change_pct: float | None) -> str:
    if trend == "rising":
        pct = f" (+{change_pct:.1f}%)" if change_pct is not None else ""
        return f"Xu hướng gần đây đang tăng{pct}."
    if trend == "underperforming":
        pct = f" ({change_pct:.1f}%)" if change_pct is not None else ""
        return f"Xu hướng gần đây đang giảm{pct} -- cân nhắc trước khi ưu tiên."
    if trend == "stable":
        return "Hiệu suất ổn định gần đây, không có biến động lớn."
    return "Chưa đủ dữ liệu trải theo thời gian để đánh giá xu hướng gần đây."


def build_recommendation(
    stats: WinnerGroupStats, trend: TrendGroupStats | None
) -> Recommendation | None:
    """None whenever the group can't be recommended at all -- insufficient
    sample (weight forced to exactly 0 either way) or no performance_score
    to build historical_performance from. Never returns a recommendation
    for a group with too little data, no matter how the other factors
    look -- see module docstring.
    """
    if stats.performance_score is None or stats.confidence == "insufficient":
        return None

    historical_performance = min(stats.performance_score / _MAX_PERFORMANCE_SCORE, 1.0)
    sample_confidence = SAMPLE_CONFIDENCE_FACTORS[stats.confidence]
    if sample_confidence == 0:
        return None

    trend_value = trend.trend if trend is not None else "insufficient_data"
    change_pct = trend.change_pct if trend is not None else None
    recency_factor = RECENCY_FACTORS[trend_value]

    weight = round(historical_performance * sample_confidence * recency_factor, 4)

    reasons = [
        _performance_reason(historical_performance, stats.performance_score),
        _sample_reason(stats.linked_sample_size, stats.confidence),
        _recency_reason(trend_value, change_pct),
    ]

    return Recommendation(
        dimension=stats.dimension,
        label=stats.label,
        weight=weight,
        historical_performance=round(historical_performance, 4),
        sample_confidence=sample_confidence,
        recency_factor=recency_factor,
        confidence_tier=stats.confidence,
        trend=trend_value,
        sample_size=stats.sample_size,
        linked_sample_size=stats.linked_sample_size,
        reasons=reasons,
    )


def rank_recommendations(
    stats_list: list[WinnerGroupStats],
    trends_by_label: dict[str, TrendGroupStats],
    limit: int | None = None,
) -> list[Recommendation]:
    recommendations = []
    for stats in stats_list:
        rec = build_recommendation(stats, trends_by_label.get(stats.label))
        if rec is not None:
            recommendations.append(rec)
    recommendations.sort(key=lambda r: r.weight, reverse=True)
    return recommendations[:limit] if limit is not None else recommendations
