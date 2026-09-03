"""News -> Factory pipeline composition root (see
docs/features/123-news-channel.md).

The one place allowed to import app.modules.news together with
app.modules.beat / app.modules.batch / app.modules.ai -- same
composition-root shape as app/api/v1/endpoints/batch_render.py (which this
file leans on directly for template lookup + batch bookkeeping). Two
actions:

  POST /news/items/draft-scripts  -- AI-write a straight news-read narration
                                     script for each selected NewsItem
  POST /news/batch                -- turn scripted NewsItems into a real
                                     Batch of Factory Projects (script
                                     pre-filled + locked), then the existing
                                     /batches/{id}/generate-beats + /render
                                     endpoints take over unchanged

No image/video generation here; the drafted Script is flattened to the
plain `script_text` string the existing beat pipeline already consumes.
"""

import concurrent.futures
import json
import logging
import threading

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.batch_render import _get_template_or_404
from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.db.session import SessionLocal
from app.modules.ai.llm_client import (
    AICredentials,
    AIProviderError,
    AIProviderTimeoutError,
    call_structured,
    resolve_ai_credentials,
)
from app.modules.batch.models import Batch, BatchItem
from app.modules.batch.schemas import BatchOut
from app.modules.batch.service import get_batch, project_name_for_item
from app.modules.beat.models import Project
from app.modules.beat.project_service import unique_project_slug
from app.modules.beat.schemas import new_project_draft
from app.modules.news import service as news_service
from app.modules.news.schemas import (
    DraftScriptsRequest,
    DraftScriptsResponse,
    NewsBatchRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TOKENS = 1400

LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "vi": "Vietnamese", "pt": "Portuguese"}

NEWS_SCRIPT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "hook": {"type": "string"},
            "body": {"type": "array", "items": {"type": "string"}},
            "ending": {"type": "string"},
        },
        "required": ["hook", "body", "ending"],
        "additionalProperties": False,
    },
}


def _build_news_prompt(language: str, target_seconds: float) -> str:
    language_name = LANGUAGE_NAMES.get(language, language)
    words = int(target_seconds * 2.4)
    return (
        "You are a news anchor writing a short spoken script for a vertical news video. "
        "You are given the headline and summary of ONE real news article.\n\n"
        "Rules:\n"
        "- Report only what the source states. Do NOT invent quotes, numbers, names, dates, "
        "outcomes, or context that is not in the source material.\n"
        "- Neutral, factual anchor tone. No opinion, no speculation, no editorializing.\n"
        "- If the source is thin, keep the script short rather than padding it with invented detail.\n"
        f"- Write entirely in {language_name}. Total length about {words} words "
        f"(~{target_seconds:.0f} seconds read aloud).\n"
        "- Attribute clearly (\"theo <nguồn>\" / \"according to reports\") when stating specifics.\n\n"
        "Return JSON only:\n"
        "- hook: one spoken sentence that states the core news up front.\n"
        "- body: 2-5 spoken sentences with the key facts, in order of importance.\n"
        "- ending: one neutral closing sentence (e.g. what happens next, or a recap). No call to action.\n"
    )


def _flatten(script: dict) -> str:
    parts = [script.get("hook", ""), *script.get("body", []), script.get("ending", "")]
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def _draft_one(credentials: AICredentials, title: str, summary: str | None, source_name: str, language: str) -> str:
    user_message = f"Source: {source_name}\nHeadline: {title}\n\nSummary:\n{(summary or '(no summary provided)')}"
    try:
        with ai_generation_semaphore:
            result = call_structured(
                credentials,
                system=_build_news_prompt(language, target_seconds=45.0),
                user_message=user_message,
                output_schema=NEWS_SCRIPT_SCHEMA,
                max_tokens=MAX_TOKENS,
                schema_name="news_script",
            )
    except AIProviderTimeoutError as exc:
        raise ExternalServiceError(f"AI provider timed out: {exc}") from exc
    except AIProviderError as exc:
        raise ExternalServiceError(f"AI provider call failed: {exc}") from exc

    if result.refused:
        raise ExternalServiceError("The model refused to write this script.")
    if not result.text:
        raise ExternalServiceError("The model returned no text.")

    try:
        script_text = _flatten(json.loads(result.text))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ExternalServiceError(f"The model returned malformed JSON: {exc}") from exc
    if not script_text.strip():
        raise ExternalServiceError("The model returned an empty script.")
    return script_text


def _draft_scripts_worker(item_ids: list[int], credentials: AICredentials, max_workers: int) -> None:
    items = news_service.get_items(item_ids)

    def _process(item) -> None:
        try:
            script_text = _draft_one(
                credentials,
                title=item.title,
                summary=item.summary,
                source_name=item.source.name if item.source is not None else "news",
                language=item.source.language if item.source is not None else "vi",
            )
            news_service.set_item_fields(item.id, script_text=script_text, status="drafted")
        except Exception:  # noqa: BLE001 -- one item failing must not abort the rest
            logger.exception("News script draft failed for item %s", item.id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        list(executor.map(_process, [i for i in items if i.status in ("new", "drafted")]))


@router.post("/news/items/draft-scripts", response_model=DraftScriptsResponse)
def draft_scripts(payload: DraftScriptsRequest, settings: Settings = Depends(get_settings)) -> DraftScriptsResponse:
    """Synchronous for a handful of items, backgrounded above ~3. Either way
    the response reports how the synchronous portion went; poll GET
    /news/items to see backgrounded results land.
    """
    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise ValidationError(
            "No AI provider is configured. Go to Settings to choose a provider and enter an API key."
        )

    items = [i for i in news_service.get_items(payload.item_ids) if i.status in ("new", "drafted")]
    if not items:
        return DraftScriptsResponse(drafted=0, failed=0, errors=["No eligible items (already queued/used/dismissed)."])

    if len(items) > 3:
        thread = threading.Thread(
            target=_draft_scripts_worker,
            args=([i.id for i in items], credentials, settings.max_concurrent_ai_generation),
            daemon=True,
        )
        thread.start()
        return DraftScriptsResponse(drafted=0, failed=0, errors=[f"Drafting {len(items)} scripts in the background."])

    drafted = 0
    errors: list[str] = []
    for item in items:
        try:
            script_text = _draft_one(
                credentials, title=item.title, summary=item.summary,
                source_name=item.source.name if item.source is not None else "news",
                language=item.source.language if item.source is not None else "vi",
            )
            news_service.set_item_fields(item.id, script_text=script_text, status="drafted")
            drafted += 1
        except ExternalServiceError as exc:
            errors.append(f"{item.title[:60]}: {exc}")
    return DraftScriptsResponse(drafted=drafted, failed=len(errors), errors=errors)


@router.post("/news/batch", response_model=BatchOut, status_code=201)
def create_news_batch(payload: NewsBatchRequest, settings: Settings = Depends(get_settings)) -> BatchOut:
    """Mirrors app/api/v1/endpoints/batch_render.py::create_batch's own
    script path (one shared session, Project + Batch + BatchItem committed
    once) -- the drafted news script becomes a locked Project.script_text,
    so the existing /batches/{id}/generate-beats + /render flow drives it
    from here with zero news-specific rendering code.
    """
    template = _get_template_or_404(payload.template_id, settings)

    items = news_service.get_items(payload.item_ids)
    by_id = {i.id: i for i in items}
    scripted = [
        by_id[i] for i in payload.item_ids
        if i in by_id and (by_id[i].script_text or "").strip() and by_id[i].status in ("new", "drafted")
    ]
    if not scripted:
        raise ValidationError(
            "None of the selected items have a drafted script yet, or they are already queued. "
            "Run \"Draft scripts\" first."
        )

    db = SessionLocal()
    try:
        batch = Batch(name=payload.name, template_id=template.id, status="DRAFT")
        db.add(batch)
        db.flush()

        created: list[tuple[int, int]] = []  # (news_item_id, project_id)
        for index, item in enumerate(scripted, start=1):
            project_name = project_name_for_item(payload.name, index)
            config_snapshot = template.config.model_copy(deep=True)
            script_text = item.script_text.strip()
            project = Project(
                name=project_name,
                slug=unique_project_slug(project_name, db),
                beat_plan_json=new_project_draft(script_text, project_name, config_snapshot),
            )
            db.add(project)
            db.flush()
            db.add(BatchItem(
                batch_id=batch.id, index=index, script_text=script_text,
                project_id=project.id, status="PROJECT_CREATED",
            ))
            created.append((item.id, project.id))

        db.commit()
        batch_id = batch.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    for news_item_id, project_id in created:
        news_service.set_item_fields(news_item_id, status="queued", project_id=project_id, batch_id=batch_id)

    return BatchOut.model_validate(get_batch(batch_id), from_attributes=True)
