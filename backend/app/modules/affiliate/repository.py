"""Query/persistence only -- no business rules, matching the split already
established by app/modules/content_strategy/repository.py (itself mirroring
app/services/library/repository.py).
"""

# ProductRepository defines a method literally named `list`, which shadows
# the builtin `list` inside this class body for every annotation evaluated
# afterward (e.g. `-> list[float]`) unless annotations are deferred --
# hence PEP 563 here.
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.publish_log import PublishLog
from app.modules.affiliate.models import AffiliateLink, AffiliateProduct


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, category: str | None = None, active_only: bool = False) -> list[AffiliateProduct]:
        query = self.db.query(AffiliateProduct)
        if category is not None:
            query = query.filter(AffiliateProduct.category == category)
        if active_only:
            query = query.filter(AffiliateProduct.active.is_(True))
        return query.order_by(AffiliateProduct.name).all()

    def get(self, product_id: int) -> AffiliateProduct | None:
        return self.db.get(AffiliateProduct, product_id)

    def total_sales_by_product(self) -> dict[int, int]:
        """Sums PublishLog.affiliate_sales (the REUSED, manually-entered
        "Order" data -- see module docstring) grouped by which Product each
        publish's linked AffiliateLink belongs to. Two queries (not a SQL
        join) since PublishLog.affiliate_link_id is a bare int with no real
        FK to affiliate_link (per app/modules/README.md's cross-module
        reference convention) -- a DB-level join across an unconstrained
        column would work by accident, not by contract.
        """
        product_by_link = {row[0]: row[1] for row in self.db.query(AffiliateLink.id, AffiliateLink.product_id).all()}
        if not product_by_link:
            return {}

        totals: dict[int, int] = {}
        rows = (
            self.db.query(PublishLog.affiliate_link_id, PublishLog.affiliate_sales)
            .filter(PublishLog.affiliate_link_id.in_(product_by_link.keys()))
            .all()
        )
        for link_id, sales in rows:
            product_id = product_by_link.get(link_id)
            if product_id is None:
                continue
            totals[product_id] = totals.get(product_id, 0) + (sales or 0)
        return totals

    def peer_prices(self, category: str, exclude_id: int | None = None) -> list[float]:
        query = self.db.query(AffiliateProduct.price).filter(
            AffiliateProduct.category == category, AffiliateProduct.price.isnot(None)
        )
        if exclude_id is not None:
            query = query.filter(AffiliateProduct.id != exclude_id)
        return [row[0] for row in query.all()]

    def create(self, product: AffiliateProduct) -> AffiliateProduct:
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def save(self, product: AffiliateProduct) -> AffiliateProduct:
        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product: AffiliateProduct) -> None:
        self.db.delete(product)
        self.db.commit()


class LinkRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_product(self, product_id: int) -> list[AffiliateLink]:
        return self.db.query(AffiliateLink).filter(AffiliateLink.product_id == product_id).order_by(AffiliateLink.created_at.desc()).all()

    def get(self, link_id: int) -> AffiliateLink | None:
        return self.db.get(AffiliateLink, link_id)

    def get_by_code(self, link_code: str) -> AffiliateLink | None:
        return self.db.query(AffiliateLink).filter(AffiliateLink.link_code == link_code).first()

    def create(self, link: AffiliateLink) -> AffiliateLink:
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    def save(self, link: AffiliateLink) -> AffiliateLink:
        self.db.commit()
        self.db.refresh(link)
        return link

    def delete(self, link: AffiliateLink) -> None:
        self.db.delete(link)
        self.db.commit()
