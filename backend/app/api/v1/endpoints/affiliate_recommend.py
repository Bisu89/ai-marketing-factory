"""Task 12 -- Affiliate Engine. Composition root: the one place allowed to
import app.modules.affiliate together with app.modules.ai.llm_client (and,
optionally, app.modules.content_strategy to resolve a ContentIdea into a
story description), per app/modules/README.md. Same "module builds the
prompt, composition root calls call_structured()" split Task 09/11 already
established.

Read-only/advisory throughout -- neither endpoint here writes anything or
attaches a product to any story/idea/publish. Per this task's own "do NOT
inject products into every story" and "keep commercial content
configurable" instructions, a human always makes the actual call (by
creating an AffiliateLink and setting PublishLog.affiliate_link_id
themselves via the existing publish-log endpoints).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.modules.affiliate import matching
from app.modules.affiliate.repository import ProductRepository
from app.modules.affiliate.schemas import CategoryRecommendationOut, ProductMatchOut
from app.modules.ai.llm_client import AIProviderError, AIProviderTimeoutError, call_structured, resolve_ai_credentials
from app.modules.content_strategy.models import ContentIdea

router = APIRouter()

MAX_TOKENS = 768


def _resolve_story_text(db: Session, story_text: str | None, content_idea_id: int | None) -> str:
    if story_text and story_text.strip():
        return story_text.strip()
    if content_idea_id is not None:
        idea = db.get(ContentIdea, content_idea_id)
        if idea is None:
            raise NotFoundError("ContentIdea", content_idea_id)
        parts = [idea.title]
        if idea.premise:
            parts.append(idea.premise)
        return " -- ".join(parts)
    raise HTTPException(status_code=400, detail="Cần story_text hoặc content_idea_id.")


def _recommend_categories(db: Session, settings: Settings, story_text: str | None, content_idea_id: int | None) -> list[dict]:
    text = _resolve_story_text(db, story_text, content_idea_id)

    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise HTTPException(status_code=400, detail="Chưa cấu hình AI provider (Anthropic/OpenAI) trong Settings.")

    system_prompt, user_message = matching.build_category_prompt(text)
    try:
        with ai_generation_semaphore:
            result = call_structured(
                credentials, system=system_prompt, user_message=user_message,
                output_schema=matching.CATEGORY_SCHEMA, max_tokens=MAX_TOKENS, schema_name="affiliate_categories",
            )
    except AIProviderTimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"AI provider timeout: {exc}") from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=f"AI provider error: {exc}") from exc

    if result.refused:
        raise HTTPException(status_code=422, detail="AI provider từ chối đề xuất category.")

    try:
        return matching.parse_category_response(result.text)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=502, detail=f"AI trả về dữ liệu không hợp lệ: {exc}") from exc


@router.post("/affiliate/recommend-categories", response_model=list[CategoryRecommendationOut])
def recommend_categories(
    story_text: str | None = None,
    content_idea_id: int | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        categories = _recommend_categories(db, settings, story_text, content_idea_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [CategoryRecommendationOut(**c) for c in categories]


@router.post("/affiliate/recommend-products", response_model=list[ProductMatchOut])
def recommend_products(
    story_text: str | None = None,
    content_idea_id: int | None = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        categories = _recommend_categories(db, settings, story_text, content_idea_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    active_products = ProductRepository(db).list(active_only=True)
    matches = matching.match_products(active_products, categories, limit=limit)
    return [
        ProductMatchOut(
            product=m.product, category_relevance=m.category_relevance, category_reason=m.category_reason,
            final_score=m.final_score, reasons=m.reasons,
        )
        for m in matches
    ]
