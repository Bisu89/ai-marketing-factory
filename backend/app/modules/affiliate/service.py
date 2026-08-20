"""Business rules for Product/Link. Two small, focused services in one
file, same shape app/modules/content_strategy/service.py already uses.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.affiliate.models import AffiliateLink, AffiliateProduct
from app.modules.affiliate.repository import LinkRepository, ProductRepository
from app.modules.affiliate.scoring import compute_product_score


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProductService:
    def __init__(self, db: Session):
        self.db = db
        self.products = ProductRepository(db)

    def list_products(self, category: str | None = None, active_only: bool = False) -> list[AffiliateProduct]:
        return self.products.list(category, active_only)

    def get_product(self, product_id: int) -> AffiliateProduct:
        product = self.products.get(product_id)
        if product is None:
            raise NotFoundError("AffiliateProduct", product_id)
        return product

    def create_product(
        self,
        *,
        name: str,
        category: str,
        affiliate_url: str,
        platform: str,
        tags: list[str] | None = None,
        price: float | None = None,
        commission_rate: float | None = None,
        rating: float | None = None,
        review_count: int | None = None,
        active: bool = True,
        notes: str | None = None,
    ) -> AffiliateProduct:
        if commission_rate is not None and not (0 <= commission_rate <= 1):
            raise ValidationError("commission_rate must be between 0 and 1.")
        if rating is not None and not (0 <= rating <= 5):
            raise ValidationError("rating must be between 0 and 5.")

        product = AffiliateProduct(
            name=name,
            category=category,
            tags=tags,
            price=price,
            commission_rate=commission_rate,
            affiliate_url=affiliate_url,
            platform=platform,
            rating=rating,
            review_count=review_count,
            active=active,
            notes=notes,
        )
        return self.products.create(product)

    def update_product(self, product_id: int, **fields) -> AffiliateProduct:
        product = self.get_product(product_id)
        if "commission_rate" in fields and fields["commission_rate"] is not None:
            if not (0 <= fields["commission_rate"] <= 1):
                raise ValidationError("commission_rate must be between 0 and 1.")
        if "rating" in fields and fields["rating"] is not None:
            if not (0 <= fields["rating"] <= 5):
                raise ValidationError("rating must be between 0 and 5.")

        for key, value in fields.items():
            if value is not None and hasattr(product, key):
                setattr(product, key, value)
        return self.products.save(product)

    def delete_product(self, product_id: int) -> None:
        product = self.get_product(product_id)
        self.products.delete(product)

    def recompute_score(self, product_id: int) -> AffiliateProduct:
        product = self.get_product(product_id)
        peer_prices = self.products.peer_prices(product.category, exclude_id=product.id)
        totals = self.products.total_sales_by_product()
        total_sales = totals.get(product.id, 0)
        max_total_sales = max(totals.values(), default=0)

        score, breakdown = compute_product_score(
            commission_rate=product.commission_rate,
            price=product.price,
            peer_prices=peer_prices,
            total_sales=total_sales,
            max_total_sales_in_catalog=max_total_sales,
            rating=product.rating,
        )
        product.product_score = score
        product.product_score_breakdown = {
            "commission_component": breakdown.commission_component,
            "price_component": breakdown.price_component,
            "demand_component": breakdown.demand_component,
            "review_component": breakdown.review_component,
            "return_risk_component": breakdown.return_risk_component,
            "notes": breakdown.notes,
        }
        product.product_score_computed_at = _utcnow()
        return self.products.save(product)


class LinkService:
    def __init__(self, db: Session):
        self.db = db
        self.links = LinkRepository(db)
        self.products = ProductRepository(db)

    def list_for_product(self, product_id: int) -> list[AffiliateLink]:
        return self.links.list_for_product(product_id)

    def create_link(self, product_id: int, label: str | None) -> AffiliateLink:
        if self.products.get(product_id) is None:
            raise NotFoundError("AffiliateProduct", product_id)
        link = AffiliateLink(product_id=product_id, label=label)
        return self.links.create(link)

    def get_link(self, link_id: int) -> AffiliateLink:
        link = self.links.get(link_id)
        if link is None:
            raise NotFoundError("AffiliateLink", link_id)
        return link

    def delete_link(self, link_id: int) -> None:
        link = self.get_link(link_id)
        self.links.delete(link)

    def record_click(self, link_code: str) -> AffiliateLink | None:
        """Real, atomic click increment -- see router.py's GET /r/{code}.
        Returns None (never raises) for an unknown code so the redirect
        endpoint can fall back to a plain 404 instead of a 500.
        """
        link = self.links.get_by_code(link_code)
        if link is None:
            return None
        link.click_count += 1
        link.last_clicked_at = _utcnow()
        return self.links.save(link)
