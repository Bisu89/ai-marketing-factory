from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AICallCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    job_id: int | None
    video_id: int
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    cost_usd: float | None
    cost_note: str | None
    confirmed_price: bool
    created_at: datetime


class GroupCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    total_cost_usd: float
    call_count: int
    unpriced_call_count: int
    all_confirmed: bool


class StoryCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    story_job_id: int
    video_id: int
    total_cost_usd: float
    call_count: int
    unpriced_call_count: int


class BatchCostOut(BaseModel):
    batch_id: int
    batch_name: str
    total_cost_usd: float
    story_count: int
    unpriced_call_count: int


class VideoCostOut(BaseModel):
    video_compose_job_id: int
    project_id: int | None
    image_cost_usd: float | None
    image_count: int | None


class AICostSummaryOut(BaseModel):
    total_ai_cost_usd: float
    total_calls: int
    unpriced_call_count: int
    videos_generated: int
    average_cost_per_video_usd: float | None
    average_cost_per_video_note: str
    cost_per_1000_videos_usd: float | None
    by_provider: list[GroupCostOut]
    by_model: list[GroupCostOut]
    by_month: list[GroupCostOut]
