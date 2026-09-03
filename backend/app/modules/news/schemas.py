"""Pydantic I/O shapes + status validation for the News module. Pure -- no
DB/FastAPI/other-module dependency.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.news.models import NEWS_ITEM_STATUSES


# -- NewsSource ----------------------------------------------------------


class NewsSourceCreateIn(BaseModel):
    name: str
    feed_url: str
    category: str | None = None
    language: str = "vi"
    enabled: bool = True

    @field_validator("name", "feed_url")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("feed_url")
    @classmethod
    def _looks_like_url(cls, value: str) -> str:
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("feed_url must start with http:// or https://")
        return value


class NewsSourceUpdateIn(BaseModel):
    name: str | None = None
    feed_url: str | None = None
    category: str | None = None
    language: str | None = None
    enabled: bool | None = None


class NewsSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    feed_url: str
    enabled: bool
    category: str | None
    language: str
    last_fetched_at: datetime | None
    last_error: str | None
    created_at: datetime | None = None
    # Filled in by the router (not a stored column): how many still-active
    # (new/drafted) items this source currently has waiting.
    pending_items: int | None = None


# -- NewsItem ----------------------------------------------------------


class NewsItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    source_name: str | None = None
    title: str
    summary: str | None
    link: str | None
    image_url: str | None
    published_at: datetime | None
    status: str
    script_text: str | None
    project_id: int | None
    batch_id: int | None
    created_at: datetime | None = None


class NewsItemListResponse(BaseModel):
    items: list[NewsItemOut]
    total: int
    page: int
    page_size: int


class NewsItemUpdateIn(BaseModel):
    status: str | None = None
    script_text: str | None = None

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str | None) -> str | None:
        if value is not None and value not in NEWS_ITEM_STATUSES:
            raise ValueError(f"status must be one of {NEWS_ITEM_STATUSES}")
        return value


# -- Fetch results ----------------------------------------------------------


class FetchResult(BaseModel):
    source_id: int
    source_name: str
    fetched: int = 0
    new_items: int = 0
    duplicates: int = 0
    error: str | None = None


class FetchAllResponse(BaseModel):
    results: list[FetchResult]
    total_new_items: int = 0


# -- News -> Factory pipeline (composition root) -------------------------


class DraftScriptsRequest(BaseModel):
    item_ids: list[int] = Field(min_length=1)


class DraftScriptsResponse(BaseModel):
    drafted: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


class NewsBatchRequest(BaseModel):
    name: str
    template_id: str
    item_ids: list[int] = Field(min_length=1)

    @field_validator("name", "template_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()
