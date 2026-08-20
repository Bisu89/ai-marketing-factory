"""Affiliate Engine (Task 12): Content -> Audience -> Product Category ->
Product -> Affiliate Link -> Click -> Order -> Commission.

Reuses, never duplicates, PublishLog's existing affiliate_product (free
text)/affiliate_sales/affiliate_revenue fields (app/models/publish_log.py)
-- those already ARE this app's "Order"/"Commission" data, manually
entered by the user after checking their real affiliate dashboard (no
generic affiliate-network API exists to pull this automatically, and
building one is out of this task's scope). This module adds the missing
structured layer on top: a real Product catalog, a real trackable
AffiliateLink (genuine click counting via a redirect endpoint -- see
router.py), and a deterministic Product Score. PublishLog gains exactly
one new bare int column, `affiliate_link_id` (no FK/import, same
"cross-reference without a real FK" convention its own existing
`ai_story_job_id` already uses), to optionally attribute a publish's
existing affiliate_sales/affiliate_revenue to a specific tracked link --
see app/db/migrate.py's _NEW_COLUMNS for the additive migration.

ContentIdea.commercial_intent (app/modules/content_strategy/models.py)
already anticipated this task by name in its own docstring ("the later
Affiliate task... is what will give this real structure") -- deliberately
left untouched here: giving it a rigid enum would require either module to
import the other (forbidden per app/modules/README.md). The actual
"commercial or organic, and configurable" switch this task requires lives
where it's real and enforceable instead: PublishLog.affiliate_link_id is
null for organic, set for commercial -- decided per-publish, by a human,
never auto-injected (see the recommend-products endpoint's own
read-only/advisory-only contract).

Own tables, no FK into core/other modules per app/modules/README.md.
"""

import secrets
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_link_code() -> str:
    return secrets.token_urlsafe(6)


class AffiliateProduct(Base):
    """One catalog entry. `product_score`/`product_score_breakdown` are
    NULL until POST /affiliate/products/{id}/recompute-score runs (see
    scoring.py) -- never a guessed number, same "null until actually
    computed" convention as StoryVersion.quality_score.
    """

    __tablename__ = "affiliate_product"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Extra free-form keywords beyond `category` itself, used by the
    # deterministic category-match step (matching.py) alongside category --
    # e.g. a "self-care" product tagged ["gift", "relaxation"].
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1
    affiliate_url: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)

    # "if available" per this task's own product-fields spec -- both stay
    # NULL (never defaulted to 0/guessed) until the user enters real data.
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-5
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    product_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    product_score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    product_score_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    links: Mapped[list["AffiliateLink"]] = relationship("AffiliateLink", back_populates="product")


class AffiliateLink(Base):
    """One trackable link for a Product -- `click_count` is a real,
    atomically-incremented counter (see router.py's GET /r/{code}), not a
    manually-typed estimate. `label` is free text ("TikTok bio link",
    "Video 42 description") since one Product may have several links
    across different placements.
    """

    __tablename__ = "affiliate_link"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("affiliate_product.id"), nullable=False, index=True)
    link_code: Mapped[str] = mapped_column(String, nullable=False, unique=True, default=_new_link_code)
    label: Mapped[str | None] = mapped_column(String, nullable=True)

    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    product: Mapped[AffiliateProduct] = relationship("AffiliateProduct", back_populates="links")
