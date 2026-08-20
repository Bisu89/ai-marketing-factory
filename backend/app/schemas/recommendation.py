from pydantic import BaseModel, ConfigDict


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: str
    label: str

    weight: float
    historical_performance: float
    sample_confidence: float
    recency_factor: float

    confidence_tier: str
    trend: str
    sample_size: int
    linked_sample_size: int

    reasons: list[str]
