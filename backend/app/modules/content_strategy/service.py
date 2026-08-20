"""Business rules for Pillar/Format/Idea. Three small, focused services in
one file -- the same shape app/services/library/service.py already uses for
VideoLibraryService/CategoryService/EmotionService/TagService -- not one
combined "ContentStrategyService"/"ContentBusinessService": each class only
knows about its own entity plus the read-only lookups (Pillar, Format,
Emotion) it needs to validate a reference against.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.emotion import Emotion
from app.modules.content_strategy.models import ContentIdea
from app.modules.content_strategy.repository import (
    FormatRepository,
    IdeaFilters,
    IdeaRepository,
    PillarRepository,
)


class PillarService:
    def __init__(self, db: Session):
        self.pillars = PillarRepository(db)

    def list(self) -> list:
        return self.pillars.list()


class FormatService:
    def __init__(self, db: Session):
        self.formats = FormatRepository(db)

    def list(self, pillar_id: int | None = None) -> list:
        return self.formats.list(pillar_id)


class IdeaService:
    def __init__(self, db: Session):
        self.db = db
        self.ideas = IdeaRepository(db)
        self.pillars = PillarRepository(db)
        self.formats = FormatRepository(db)

    def _validate_create_refs(self, pillar_id: int, format_id: int, target_emotion_id: int | None) -> None:
        if self.pillars.get(pillar_id) is None:
            raise NotFoundError("Content pillar", pillar_id)

        fmt = self.formats.get(format_id)
        if fmt is None:
            raise NotFoundError("Content format", format_id)
        if fmt.pillar_id != pillar_id:
            raise ValidationError(f"Format {format_id} does not belong to pillar {pillar_id}")

        if target_emotion_id is not None and self.db.get(Emotion, target_emotion_id) is None:
            raise NotFoundError("Emotion", target_emotion_id)

    def list_ideas(
        self,
        pillar_id: int | None = None,
        format_id: int | None = None,
        status: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ContentIdea], int]:
        filters = IdeaFilters(
            pillar_id=pillar_id,
            format_id=format_id,
            status=status,
            min_score=min_score,
            max_score=max_score,
            page=page,
            page_size=page_size,
        )
        return self.ideas.list(filters)

    def get_idea(self, idea_id: int) -> ContentIdea:
        idea = self.ideas.get(idea_id)
        if idea is None:
            raise NotFoundError("Content idea", idea_id)
        return idea

    def create_idea(
        self,
        pillar_id: int,
        format_id: int,
        title: str,
        premise: str | None,
        target_emotion_id: int | None,
        commercial_intent: str | None,
        status: str,
    ) -> ContentIdea:
        self._validate_create_refs(pillar_id, format_id, target_emotion_id)
        idea = ContentIdea(
            pillar_id=pillar_id,
            format_id=format_id,
            title=title,
            premise=premise,
            target_emotion_id=target_emotion_id,
            commercial_intent=commercial_intent,
            status=status,
        )
        return self.ideas.create(idea)

    def update_idea(
        self,
        idea_id: int,
        title: str | None = None,
        premise: str | None = None,
        target_emotion_id: int | None = None,
        commercial_intent: str | None = None,
        score: float | None = None,
        status: str | None = None,
    ) -> ContentIdea:
        idea = self.get_idea(idea_id)

        if target_emotion_id is not None and self.db.get(Emotion, target_emotion_id) is None:
            raise NotFoundError("Emotion", target_emotion_id)

        if title is not None:
            idea.title = title
        if premise is not None:
            idea.premise = premise
        if target_emotion_id is not None:
            idea.target_emotion_id = target_emotion_id
        if commercial_intent is not None:
            idea.commercial_intent = commercial_intent
        if score is not None:
            idea.score = score
        if status is not None:
            idea.status = status

        return self.ideas.save(idea)

    def delete_idea(self, idea_id: int) -> None:
        idea = self.get_idea(idea_id)
        self.ideas.delete(idea)
