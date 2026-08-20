"""Query/persistence only -- no business rules, matching the split already
established by app/services/library/repository.py (business rules --
status transitions, cross-entity validation -- live in service.py).
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.content_strategy.models import ContentFormat, ContentIdea, ContentPillar


class PillarRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[ContentPillar]:
        return self.db.query(ContentPillar).order_by(ContentPillar.name).all()

    def get(self, pillar_id: int) -> ContentPillar | None:
        return self.db.get(ContentPillar, pillar_id)


class FormatRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, pillar_id: int | None = None) -> list[ContentFormat]:
        query = self.db.query(ContentFormat)
        if pillar_id is not None:
            query = query.filter(ContentFormat.pillar_id == pillar_id)
        return query.order_by(ContentFormat.name).all()

    def get(self, format_id: int) -> ContentFormat | None:
        return self.db.get(ContentFormat, format_id)


@dataclass
class IdeaFilters:
    pillar_id: int | None = None
    format_id: int | None = None
    status: str | None = None
    min_score: float | None = None
    max_score: float | None = None
    page: int = 1
    page_size: int = 50


class IdeaRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, filters: IdeaFilters) -> tuple[list[ContentIdea], int]:
        query = self.db.query(ContentIdea)

        if filters.pillar_id is not None:
            query = query.filter(ContentIdea.pillar_id == filters.pillar_id)
        if filters.format_id is not None:
            query = query.filter(ContentIdea.format_id == filters.format_id)
        if filters.status is not None:
            query = query.filter(ContentIdea.status == filters.status)
        if filters.min_score is not None:
            query = query.filter(ContentIdea.score >= filters.min_score)
        if filters.max_score is not None:
            query = query.filter(ContentIdea.score <= filters.max_score)

        total = query.count()

        query = query.order_by(ContentIdea.created_at.desc())

        page = max(filters.page, 1)
        page_size = max(1, min(filters.page_size, 200))
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    def get(self, idea_id: int) -> ContentIdea | None:
        return self.db.get(ContentIdea, idea_id)

    def create(self, idea: ContentIdea) -> ContentIdea:
        self.db.add(idea)
        self.db.commit()
        self.db.refresh(idea)
        return idea

    def save(self, idea: ContentIdea) -> ContentIdea:
        self.db.commit()
        self.db.refresh(idea)
        return idea

    def delete(self, idea: ContentIdea) -> None:
        self.db.delete(idea)
        self.db.commit()
