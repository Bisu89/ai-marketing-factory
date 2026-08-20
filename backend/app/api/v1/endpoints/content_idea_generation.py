"""Composition root connecting Content Strategy
(app.modules.content_strategy) to the existing AI Story/Hook generation
modules (app.modules.ai.story, app.modules.ai.hook) -- Task 04. Neither
module may import the other (per app/modules/README.md); this file is the
one place allowed to import both, mirroring content_generate.py's/
factory_pipeline.py's own "composition root importing multiple modules"
pattern.

Does not create a ContentStory/ContentHook table, does not duplicate
ai_generation_history, does not replace the existing Claude/OpenAI client,
and is not a global orchestrator -- it only builds one extra text block
(the selected ContentIdea's pillar/format/premise/target emotion/
commercial intent) and hands it to StoryService.generate()'s/
HookService.generate()'s own new optional `extra_context` parameter.
Every existing entry point (POST /story-jobs, POST /hook-jobs, and manual
generation with no idea at all) is unaffected -- extra_context defaults to
None there, producing byte-identical prompts to before this task.

Flow this enables (Task 04's own brief):
    Content Idea -> generate Story (this file) -> select StoryVersion
    (existing POST /story-jobs/{id}/versions/{id}/select, untouched)
    -> generate Hooks (this file) -> select HookVersion (existing
    POST /hook-jobs/{id}/hooks/{id}/favorite, untouched)
    -> continue into the existing video pipeline exactly as before.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.emotion import Emotion
from app.modules.ai.hook.schemas import HookJobOut
from app.modules.ai.hook.schemas import job_to_out as hook_job_to_out
from app.modules.ai.hook.service import HookService
from app.modules.ai.llm_client import resolve_ai_credentials
from app.modules.ai.story.schemas import StoryJobOut
from app.modules.ai.story.schemas import job_to_out as story_job_to_out
from app.modules.ai.story.service import StoryService
from app.modules.content_strategy.models import ContentFormat, ContentIdea, ContentPillar

router = APIRouter()


class IdeaStoryGenerateIn(BaseModel):
    video_id: int
    style: str
    language: str = "english"


class IdeaHookGenerateIn(BaseModel):
    video_id: int


def _load_idea_context(db: Session, idea_id: int) -> tuple[ContentIdea, str]:
    """Fetches the ContentIdea plus its Pillar/Format/Emotion names (all
    read-only lookups, no writes) and renders them into the one extra text
    block every generation call in this file passes as `extra_context`.
    """
    idea = db.get(ContentIdea, idea_id)
    if idea is None:
        raise NotFoundError("Content idea", idea_id)

    pillar = db.get(ContentPillar, idea.pillar_id)
    fmt = db.get(ContentFormat, idea.format_id)
    emotion = db.get(Emotion, idea.target_emotion_id) if idea.target_emotion_id is not None else None

    lines = [
        "Content strategy context (from an approved Content Idea -- follow this direction faithfully):",
        f"- Pillar: {pillar.name if pillar else 'N/A'}",
        f"- Format: {fmt.name if fmt else 'N/A'}",
        f"- Premise: {idea.premise or 'N/A'}",
        f"- Target emotion: {emotion.name if emotion else 'N/A'}",
        f"- Commercial intent: {idea.commercial_intent or 'N/A'}",
    ]
    return idea, "\n".join(lines)


def get_story_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> StoryService:
    return StoryService(db, resolve_ai_credentials(settings))


def get_hook_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> HookService:
    return HookService(db, resolve_ai_credentials(settings))


@router.post("/content-ideas/{idea_id}/generate-story", response_model=StoryJobOut, status_code=201)
def generate_story_from_idea(
    idea_id: int,
    payload: IdeaStoryGenerateIn,
    db: Session = Depends(get_db),
    service: StoryService = Depends(get_story_service),
):
    idea, context = _load_idea_context(db, idea_id)
    job = service.generate(
        video_id=payload.video_id,
        style=payload.style,
        language=payload.language,
        extra_context=context,
        content_idea_id=idea.id,
    )
    return story_job_to_out(job)


@router.post("/content-ideas/{idea_id}/generate-hooks", response_model=HookJobOut, status_code=201)
def generate_hooks_from_idea(
    idea_id: int,
    payload: IdeaHookGenerateIn,
    db: Session = Depends(get_db),
    service: HookService = Depends(get_hook_service),
):
    _idea, context = _load_idea_context(db, idea_id)
    job = service.generate(video_id=payload.video_id, extra_context=context)
    return hook_job_to_out(job)
