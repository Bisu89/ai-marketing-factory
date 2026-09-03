"""News -> Factory pipeline composition root (see
docs/features/123-news-channel.md).

The one place allowed to import app.modules.news together with
app.modules.beat / app.modules.batch / app.modules.ai / app.modules.asset
-- same composition-root shape as app/api/v1/endpoints/batch_render.py
(which this file leans on for template lookup + batch bookkeeping).

  POST /news/items/draft-scripts  -- AI-write a neutral news-read narration
                                     script for each selected NewsItem
  POST /news/batch                -- one Factory Project per scripted item;
                                     when use_article_image is on, the
                                     item's own RSS photo is downloaded +
                                     cropped and its beats are pre-built
                                     from the drafted script (no AI beat
                                     split, no library/AI image match)
  POST /news/digest               -- ONE "điểm tin" roundup video from N
                                     items: AI writes intro + one summary
                                     per story + outro; each story segment
                                     shows that story's own photo

Prefer producing these batches via the Factory engine
(POST /batches/{id}/factory-run) so the template's real voice (e.g.
vi-VN-NamMinhNeural) is used -- the classic Render All path hardcodes an
English voice.
"""

import concurrent.futures
import json
import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.batch_render import _get_template_or_404
from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.render_profile import get_render_profile
from app.db.session import SessionLocal
from app.modules.ai.llm_client import (
    AICredentials,
    AIProviderError,
    AIProviderTimeoutError,
    call_structured,
    resolve_ai_credentials,
)
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.batch.models import Batch, BatchItem
from app.modules.batch.schemas import BatchOut
from app.modules.batch.service import get_batch, project_name_for_item
from app.modules.beat.models import Project
from app.modules.beat.project_service import unique_project_slug
from app.modules.beat.schemas import Beat, BeatPlan, BeatType, ProjectConfig, new_project_draft
from app.modules.news import service as news_service
from app.modules.news.images import prepare_article_image
from app.modules.news.schemas import (
    DraftScriptsRequest,
    DraftScriptsResponse,
    NewsBatchRequest,
    NewsDigestRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TOKENS = 1400
DIGEST_MAX_TOKENS = 3000

LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "vi": "Vietnamese", "pt": "Portuguese"}

# Beat timing for pre-built news beats -- a rough words/second read rate,
# clamped so no single paragraph is an unusably short flash or a 20s hold.
# The Voice stage re-times every beat to the real synthesized narration
# anyway (see docs/features/48/58), so this is only the pre-voice estimate.
_WORDS_PER_SEC = 2.3
_MIN_BEAT_SEC = 1.8
_MAX_BEAT_SEC = 12.0


# -- Single-story news script (unchanged) ---------------------------------

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


def _call_structured_json(credentials: AICredentials, *, system: str, user: str, schema: dict, name: str, max_tokens: int) -> dict:
    try:
        with ai_generation_semaphore:
            result = call_structured(
                credentials, system=system, user_message=user,
                output_schema=schema, max_tokens=max_tokens, schema_name=name,
            )
    except AIProviderTimeoutError as exc:
        raise ExternalServiceError(f"AI provider timed out: {exc}") from exc
    except AIProviderError as exc:
        raise ExternalServiceError(f"AI provider call failed: {exc}") from exc
    if result.refused:
        raise ExternalServiceError("The model refused this request.")
    if not result.text:
        raise ExternalServiceError("The model returned no text.")
    try:
        return json.loads(result.text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ExternalServiceError(f"The model returned malformed JSON: {exc}") from exc


def _draft_one(credentials: AICredentials, title: str, summary: str | None, source_name: str, language: str) -> str:
    parsed = _call_structured_json(
        credentials,
        system=_build_news_prompt(language, target_seconds=45.0),
        user=f"Source: {source_name}\nHeadline: {title}\n\nSummary:\n{(summary or '(no summary provided)')}",
        schema=NEWS_SCRIPT_SCHEMA, name="news_script", max_tokens=MAX_TOKENS,
    )
    script_text = _flatten(parsed)
    if not script_text.strip():
        raise ExternalServiceError("The model returned an empty script.")
    return script_text


def _draft_scripts_worker(item_ids: list[int], credentials: AICredentials, max_workers: int) -> None:
    items = news_service.get_items(item_ids)

    def _process(item) -> None:
        try:
            script_text = _draft_one(
                credentials, title=item.title, summary=item.summary,
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
    """Synchronous for a handful of items, backgrounded above ~3. Poll GET
    /news/items to see backgrounded results land.
    """
    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise ValidationError("No AI provider is configured. Go to Settings to choose a provider and enter an API key.")

    items = [i for i in news_service.get_items(payload.item_ids) if i.status in ("new", "drafted")]
    if not items:
        return DraftScriptsResponse(drafted=0, failed=0, errors=["No eligible items (already queued/used/dismissed)."])

    if len(items) > 3:
        threading.Thread(
            target=_draft_scripts_worker,
            args=([i.id for i in items], credentials, settings.max_concurrent_ai_generation),
            daemon=True,
        ).start()
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


# -- Digest ("điểm tin") script -----------------------------------------

DIGEST_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "intro": {"type": "string"},
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"narration": {"type": "string"}},
                    "required": ["narration"],
                    "additionalProperties": False,
                },
            },
            "outro": {"type": "string"},
        },
        "required": ["intro", "segments", "outro"],
        "additionalProperties": False,
    },
}


def _build_digest_prompt(language: str, story_count: int) -> str:
    language_name = LANGUAGE_NAMES.get(language, language)
    return (
        "You are a news anchor writing a spoken script for a short 'news roundup' / 'điểm tin' video. "
        f"You are given {story_count} real news articles (headline + summary), numbered and in order.\n\n"
        "Rules:\n"
        "- Report only what each source states. Do NOT invent quotes, numbers, names, dates or outcomes.\n"
        "- Neutral, factual anchor tone. No opinion.\n"
        f"- Write entirely in {language_name}.\n"
        "- intro: one or two sentences opening the roundup (e.g. \"Điểm tin hôm nay\").\n"
        "- segments: EXACTLY one object per article, in the SAME order, each with `narration` = "
        "1-3 spoken sentences summarizing that article's key facts. Attribute when stating specifics.\n"
        "- outro: one neutral closing sentence. No call to action.\n\n"
        "Return JSON only, matching the schema."
    )


def _generate_digest(credentials: AICredentials, items: list, language: str) -> tuple[str, list[str], str]:
    numbered = "\n\n".join(
        f"[{n}] {it.title}\n{(it.summary or '(no summary)')}" for n, it in enumerate(items, start=1)
    )
    parsed = _call_structured_json(
        credentials,
        system=_build_digest_prompt(language, len(items)),
        user=numbered, schema=DIGEST_SCHEMA, name="news_digest", max_tokens=DIGEST_MAX_TOKENS,
    )
    intro = (parsed.get("intro") or "").strip()
    outro = (parsed.get("outro") or "").strip()
    segments = [(s.get("narration") or "").strip() for s in parsed.get("segments", [])]
    if not intro or not outro or not segments:
        raise ExternalServiceError("The digest response was missing an intro, outro, or segments.")
    # Pad/trim so segment count matches the story count exactly -- each
    # story segment must line up with its own photo.
    if len(segments) < len(items):
        segments += [items[i].title for i in range(len(segments), len(items))]
    segments = segments[: len(items)]
    return intro, segments, outro


# -- Shared: image download + beat construction ------------------------


def _register_news_image(db, path: Path, width: int, height: int) -> int:
    resolved = str(path.expanduser().resolve())
    existing = db.query(Asset).filter(Asset.path == resolved).first()
    if existing is not None:
        return existing.id
    asset = AssetService(db).register(
        AssetRegisterIn(
            filename=path.name, path=resolved, type="image",
            width=width, height=height, source="news_image",
        )
    )
    return asset.id


def _download_item_image(db, item, dest: Path, width: int, height: int) -> int | None:
    """Download the item's RSS image, crop to the render size, register it
    as a local Asset. Returns the asset id, or None on any failure (bad
    URL, not an image, too small) -- the caller then falls back to the
    normal library/AI image flow for that item.
    """
    if not item.image_url:
        return None
    try:
        if not prepare_article_image(item.image_url, dest, width, height):
            return None
        return _register_news_image(db, dest, width, height)
    except Exception:  # noqa: BLE001 -- never let one bad image abort a batch
        logger.exception("News image prepare/register failed for item %s", item.id)
        return None


def _estimate_duration(text: str) -> float:
    words = max(1, len((text or "").split()))
    return max(_MIN_BEAT_SEC, min(_MAX_BEAT_SEC, words / _WORDS_PER_SEC))


def _paragraphs(script_text: str) -> list[str]:
    return [p.strip() for p in (script_text or "").split("\n\n") if p.strip()]


def _build_beats(segments: list[tuple[str, int | None]]) -> list[Beat]:
    """segments: ordered (narration, asset_id) pairs -> one Beat each.
    First beat HOOK, last ENDING, the rest BODY.
    """
    beats: list[Beat] = []
    n = len(segments)
    for i, (narration, asset_id) in enumerate(segments, start=1):
        beat_type = BeatType.HOOK if i == 1 else BeatType.ENDING if i == n else BeatType.BODY
        beats.append(Beat(
            id=f"beat_{i:02d}", order=i, type=beat_type,
            narration=narration, duration=round(_estimate_duration(narration), 2),
            asset_id=asset_id,
        ))
    return beats


def _prebuilt_plan_json(script_text: str, beats: list[Beat], project_name: str, config: ProjectConfig) -> dict:
    plan = BeatPlan(
        script_text=script_text, beats=beats, project_name=project_name,
        config=config, script_locked=True,
    )
    return plan.model_dump(mode="json")


def _news_image_path(settings: Settings, project_name_slug: str, key: str) -> Path:
    return Path(settings.library_dir) / "_news" / project_name_slug / f"{key}.jpg"


# -- POST /news/batch --------------------------------------------------


@router.post("/news/batch", response_model=BatchOut, status_code=201)
def create_news_batch(payload: NewsBatchRequest, settings: Settings = Depends(get_settings)) -> BatchOut:
    """One Factory Project per scripted item. With use_article_image on, the
    item's RSS photo is downloaded/cropped and the project's beats are
    pre-built from the drafted script paragraphs (BatchItem -> BEATS_READY,
    so classic Generate Beats skips it). Otherwise the item falls back to
    the plain script -> Generate Beats flow (BatchItem -> PROJECT_CREATED).
    Produce the batch via POST /batches/{id}/factory-run.
    """
    template = _get_template_or_404(payload.template_id, settings)
    profile = get_render_profile(template.config.render.profile)

    by_id = {i.id: i for i in news_service.get_items(payload.item_ids)}
    scripted = [
        by_id[i] for i in dict.fromkeys(payload.item_ids)
        if i in by_id and (by_id[i].script_text or "").strip() and by_id[i].status in ("new", "drafted")
    ]
    if not scripted:
        raise ValidationError(
            'None of the selected items have a drafted script yet, or they are already queued. '
            'Run "Tạo script" first.'
        )

    db = SessionLocal()
    try:
        batch = Batch(name=payload.name, template_id=template.id, status="DRAFT")
        db.add(batch)
        db.flush()

        created: list[tuple[int, int]] = []
        for index, item in enumerate(scripted, start=1):
            project_name = project_name_for_item(payload.name, index)
            slug = unique_project_slug(project_name, db)
            config_snapshot = template.config.model_copy(deep=True)
            script_text = item.script_text.strip()

            asset_id = None
            if payload.use_article_image:
                asset_id = _download_item_image(
                    db, item, _news_image_path(settings, slug, "image"), profile.width, profile.height
                )

            if asset_id is not None:
                paras = _paragraphs(script_text) or [script_text]
                beats = _build_beats([(p, asset_id) for p in paras])
                beat_plan_json = _prebuilt_plan_json(script_text, beats, project_name, config_snapshot)
                item_status = "BEATS_READY"
            else:
                beat_plan_json = new_project_draft(script_text, project_name, config_snapshot)
                item_status = "PROJECT_CREATED"

            project = Project(name=project_name, slug=slug, beat_plan_json=beat_plan_json)
            db.add(project)
            db.flush()
            db.add(BatchItem(
                batch_id=batch.id, index=index, script_text=script_text,
                project_id=project.id, status=item_status,
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


# -- POST /news/digest ------------------------------------------------


@router.post("/news/digest", response_model=BatchOut, status_code=201)
def create_news_digest(payload: NewsDigestRequest, settings: Settings = Depends(get_settings)) -> BatchOut:
    """ONE roundup video from N items. AI writes intro + one summary per
    story + outro; each story segment's beat shows that story's own photo.
    Produces a 1-item Batch (BatchItem -> BEATS_READY); produce it via
    POST /batches/{id}/factory-run.
    """
    template = _get_template_or_404(payload.template_id, settings)
    profile = get_render_profile(template.config.render.profile)
    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise ValidationError("No AI provider is configured. Go to Settings to choose a provider and enter an API key.")

    by_id = {i.id: i for i in news_service.get_items(payload.item_ids)}
    ordered_ids = list(dict.fromkeys(payload.item_ids))  # de-dupe, preserve order
    items = [by_id[i] for i in ordered_ids if i in by_id and by_id[i].status in ("new", "drafted")]
    if len(items) < 2:
        raise ValidationError("Select at least 2 items that are not already queued.")

    language = items[0].source.language if items[0].source is not None else "vi"
    intro, segments, outro = _generate_digest(credentials, items, language)

    project_name = payload.name
    slug = None
    db = SessionLocal()
    try:
        slug = unique_project_slug(project_name, db)

        # One photo per story, downloaded up front so a failed download just
        # leaves that segment's beat image-less (soft, same as a library miss).
        story_assets: list[int | None] = [
            _download_item_image(db, item, _news_image_path(settings, slug, f"story_{n:02d}"), profile.width, profile.height)
            if payload.use_article_image else None
            for n, item in enumerate(items, start=1)
        ]

        segs: list[tuple[str, int | None]] = [(intro, story_assets[0])]
        for narration, asset_id in zip(segments, story_assets):
            segs.append((narration, asset_id))
        segs.append((outro, story_assets[-1]))

        beats = _build_beats(segs)
        script_text = "\n\n".join(s[0] for s in segs)
        config_snapshot = template.config.model_copy(deep=True)
        beat_plan_json = _prebuilt_plan_json(script_text, beats, project_name, config_snapshot)

        batch = Batch(name=payload.name, template_id=template.id, status="DRAFT")
        db.add(batch)
        db.flush()

        project = Project(name=project_name, slug=slug, beat_plan_json=beat_plan_json)
        db.add(project)
        db.flush()
        db.add(BatchItem(
            batch_id=batch.id, index=1, script_text=script_text, project_id=project.id, status="BEATS_READY",
        ))
        db.commit()
        batch_id, project_id = batch.id, project.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    for item in items:
        news_service.set_item_fields(item.id, status="queued", project_id=project_id, batch_id=batch_id)

    return BatchOut.model_validate(get_batch(batch_id), from_attributes=True)
