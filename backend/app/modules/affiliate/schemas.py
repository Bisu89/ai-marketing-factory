from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ProductCreateIn(BaseModel):
    name: str
    category: str
    affiliate_url: str
    platform: str
    tags: list[str] | None = None
    price: float | None = None
    commission_rate: float | None = None
    rating: float | None = None
    review_count: int | None = None
    active: bool = True
    notes: str | None = None

    @field_validator("name", "category", "affiliate_url", "platform")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class ProductUpdateIn(BaseModel):
    name: str | None = None
    category: str | None = None
    affiliate_url: str | None = None
    platform: str | None = None
    tags: list[str] | None = None
    price: float | None = None
    commission_rate: float | None = None
    rating: float | None = None
    review_count: int | None = None
    active: bool | None = None
    notes: str | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    tags: list[str] | None
    price: float | None
    commission_rate: float | None
    affiliate_url: str
    platform: str
    rating: float | None
    review_count: int | None
    active: bool
    notes: str | None
    product_score: float | None
    product_score_breakdown: dict | None
    product_score_computed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LinkCreateIn(BaseModel):
    label: str | None = None


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    link_code: str
    label: str | None
    click_count: int
    last_clicked_at: datetime | None
    created_at: datetime


class CategoryRecommendationOut(BaseModel):
    category: str
    relevance: float
    reason: str


class ProductMatchOut(BaseModel):
    product: ProductOut
    category_relevance: float
    category_reason: str
    final_score: float | None
    reasons: list[str]
