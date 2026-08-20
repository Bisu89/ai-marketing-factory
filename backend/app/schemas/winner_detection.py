from pydantic import BaseModel, ConfigDict


class WinnerGroupStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: str
    label: str

    sample_size: int
    linked_sample_size: int
    min_sample_size: int
    meets_minimum_sample: bool
    confidence: str

    avg_views: float | None
    median_views: float | None
    avg_engagement_rate: float | None
    avg_share_rate: float | None
    avg_follower_conversion_rate: float | None
    avg_views_per_day_since_publish: float | None

    performance_score: float | None
    performance_score_basis: str
    note: str | None


class TrendGroupStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: str
    label: str
    trend: str
    earlier_avg_score: float | None
    recent_avg_score: float | None
    change_pct: float | None
    note: str
