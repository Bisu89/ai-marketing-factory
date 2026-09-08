"""Pydantic request/response shapes for the Radar API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.discovery.contracts import ALL_PLATFORMS
from app.modules.discovery.orchestrator import SORT_KEYS


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    platforms: list[str] | None = None
    sort: str = "best"
    max_age_days: int | None = Field(default=365, ge=1, le=3650)
    limit_per_query: int = Field(default=25, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be blank")
        return v

    @field_validator("platforms")
    @classmethod
    def _known_platforms(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        bad = [p for p in v if p not in ALL_PLATFORMS]
        if bad:
            raise ValueError(f"unknown platform(s): {', '.join(bad)}")
        return v

    @field_validator("sort")
    @classmethod
    def _known_sort(cls, v: str) -> str:
        if v not in SORT_KEYS:
            raise ValueError(f"sort must be one of {', '.join(SORT_KEYS)}")
        return v


class ScoreBreakdown(BaseModel):
    relevance: float
    engagement: float
    recency: float
    short_form: float
    content_signals: float


class ResultOut(BaseModel):
    id: int
    platform: str
    source_url: str
    title: str
    description: str | None
    thumbnail_url: str | None
    creator_name: str | None
    creator_url: str | None
    published_at: datetime | None
    duration_sec: int | None
    views: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    width: int | None
    height: int | None
    aspect_ratio: float | None
    content_tags: list[str]
    also_on: list[str]
    viral_score: float
    score_breakdown: ScoreBreakdown
    rights_status: str
    attribution: str | None
    download_capability: str
    saved_video_id: int | None
    collection: str | None
    notes: str | None


class EngineStatusOut(BaseModel):
    platform: str
    status: str
    result_count: int
    error: str | None


class SearchResultOut(BaseModel):
    id: int
    query: str
    normalized_query: str
    expanded_queries: list[str]
    engine_statuses: list[EngineStatusOut]
    total_before_dedup: int
    unique_count: int
    results: list[ResultOut]
    created_at: datetime


class SearchSummaryOut(BaseModel):
    id: int
    query: str
    result_count: int
    created_at: datetime


DEFAULT_COLLECTIONS = (
    "Beard", "Funny", "Couple", "Family", "Transformation", "Reaction", "Other",
)


class SaveResultRequest(BaseModel):
    collection: str = Field(default="Other", min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("collection")
    @classmethod
    def _clean_collection(cls, v: str) -> str:
        return v.strip() or "Other"


class SaveResultOut(BaseModel):
    result_id: int
    saved: bool
    collection: str | None
    notes: str | None


class SavedResultOut(ResultOut):
    search_id: int
    query: str
    discovered_at: datetime


class FindSimilarOut(BaseModel):
    keywords: list[str]
    search: SearchResultOut
