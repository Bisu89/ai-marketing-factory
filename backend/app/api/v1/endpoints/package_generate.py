"""Ready-to-Post Package (Task 27 -- see
docs/features/53-thumbnail-metadata-package.md): the composition-root
adapter between app.modules.thumbnail/app.modules.metadata (pure logic,
see those modules' own docstrings) and app.modules.beat/video_composer.
Same composition-root shape as caption_generate.py/audio_generate.py.

final.mp4 (Task 26's own Final Composer output) is the one and only
source for the thumbnail (section 4/5 -- no AI image generation, ever);
title/description/hashtags are, by default, derived entirely from content
this Factory already produced (ContentBrief, the HOOK beat's own
narration) or an explicit manual override -- never a new AI/LLM call
(section 22/25). Real user follow-up: PackageProjectConfig.ai_metadata_enabled
is an opt-in exception to that -- a real, billed LLM call rewriting
title/description/thumbnail_text for a punchier result (see
_generate_ai_metadata below); manual overrides still win over it.

Produces two standalone, user-facing artifacts next to the project's own
final.mp4 (`thumbnail.jpg`, `metadata.json`) plus a private cache sidecar
(`package.meta.json`) -- matches Task 24/25's own "sidecar JSON metadata,
atomic tmp-then-replace write" convention exactly.
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.core.render_profile import get_render_profile
from app.db.session import SessionLocal
from app.modules.ai.llm_client import AIProviderError, AIProviderTimeoutError, call_structured, resolve_ai_credentials
from app.modules.beat.project_service import _UNSET, get_project_draft, set_project_package_overrides
from app.modules.beat.schemas import Beat, BeatType, PackageProjectConfig, ProjectOut
from app.modules.metadata.schemas import ContentInputs, MetadataError, PackageMetadata
from app.modules.metadata.service import (
    derive_category,
    derive_description,
    derive_hashtags,
    derive_title,
    normalize_hashtags,
)
from app.modules.thumbnail.renderer import (
    ENGINE_VERSION as THUMBNAIL_ENGINE_VERSION,
    build_thumbnail,
    save_thumbnail,
    select_thumbnail_frame,
    shorten_headline,
    validate_thumbnail,
)
from app.modules.thumbnail.schemas import ThumbnailConfig, ThumbnailError
from app.modules.video_composer.models import VideoComposeJob

logger = logging.getLogger(__name__)
router = APIRouter()

METADATA_ENGINE_VERSION = "post-package-v1"
# v2: the AI metadata prompt now pins the output language to the project's
# own content language instead of a soft "same language as the script"
# hint that a hardcoded "Vietnamese storytelling channel" framing kept
# overriding (real user report: English videos getting Vietnamese titles).
# v3 (feature 126): the AI call now also returns a `hashtags` array; a v2
# cache has no hashtags, so bumping the version re-runs it once with the
# hashtag-aware engine (this is the intended invalidation mechanism --
# regenerate-metadata still reuses a same-version cache, never re-bills for
# unchanged text).
AI_METADATA_ENGINE_VERSION = "package-ai-metadata-v3"

# Same map as content_generate.LANGUAGE_NAMES / story.service -- duplicated
# (a few string constants across an endpoint boundary) rather than imported.
_LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "vi": "Vietnamese", "pt": "Portuguese"}

_THUMBNAIL_FILENAME = "thumbnail.jpg"
_METADATA_FILENAME = "metadata.json"
_CACHE_FILENAME = "package.meta.json"


# -- Package incompleteness / validation error codes (section 50) ---------

PACKAGE_INCOMPLETE = "PACKAGE_INCOMPLETE"
PACKAGE_VALIDATION_FAILED = "PACKAGE_VALIDATION_FAILED"


class PackageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# -- Locating the completed render's own output directory -----------------


def _completed_render_job(project_id: int, render_job_id: int | None) -> VideoComposeJob | None:
    """Section 33/53: the Package stage's one required upstream input is a
    genuinely COMPLETED render -- not merely "a render_job_id exists on
    Project" (that field is set the instant a job is *queued*, well before
    it finishes, see factory_pipeline.py's own _stage_render). Returns
    None (never raises) for "nothing to package yet" -- the same lenient
    convention Voice/Motion/Audio/Captions already use for their own
    not-ready-yet case.
    """
    if render_job_id is None:
        return None
    db = SessionLocal()
    try:
        job = db.get(VideoComposeJob, render_job_id)
        if job is None or job.status != "completed" or not job.output_path:
            return None
        db.expunge(job)
        return job
    finally:
        db.close()


def _output_dir(job: VideoComposeJob) -> Path:
    return Path(job.output_path).parent


def thumbnail_path(job: VideoComposeJob) -> Path:
    return _output_dir(job) / _THUMBNAIL_FILENAME


def metadata_path(job: VideoComposeJob) -> Path:
    return _output_dir(job) / _METADATA_FILENAME


def _cache_path(job: VideoComposeJob) -> Path:
    return _output_dir(job) / _CACHE_FILENAME


def _read_render_metadata(job: VideoComposeJob) -> dict:
    path = Path(job.output_path).with_name("render_metadata.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _load_cache(job: VideoComposeJob) -> dict | None:
    path = _cache_path(job)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(job: VideoComposeJob, **fields) -> None:
    _cache_path(job).write_text(json.dumps(fields, indent=2), encoding="utf-8")


# -- Content inputs (section 21/24/26) -------------------------------------


def _hook_text(beats: list[Beat]) -> str | None:
    hook_beats = [b for b in sorted(beats, key=lambda b: b.order) if b.type == BeatType.HOOK and b.narration and b.narration.strip()]
    return hook_beats[0].narration if hook_beats else None


def build_content_inputs(draft: ProjectOut) -> ContentInputs:
    brief = draft.content_brief
    return ContentInputs(
        core_message=brief.core_message if brief else None,
        cta=brief.cta if brief else None,
        topic=brief.topic if brief else None,
        angle=brief.angle if brief else None,
        emotion=brief.emotion if brief else None,
        tone=brief.tone if brief else None,
        hook_text=_hook_text(draft.beats),
        project_name=draft.project_name,
    )


# -- AI Metadata (opt-in) -- real user report ------------------------------
#
# Real user report: the deterministic title/description (a truncated
# core_message) and the thumbnail's echoed-title headline all felt bland.
# Opt-in via PackageProjectConfig.ai_metadata_enabled -- unlike every other
# artifact this stage produces, this is a real, billed AI call, so it must
# never run silently by default and must never be repeated for unchanged
# content (see _resolve_ai_metadata's own cache-fingerprint reasoning).


@dataclass
class AIMetadata:
    title: str
    description: str
    thumbnail_text: str
    # Short, real hashtags the AI proposed (1-2 words each). Empty for a
    # cache written before this field existed -- AIMetadata(**old_cache)
    # still constructs, and the metadata generator falls back to the
    # deterministic derive_hashtags() when this is empty.
    hashtags: list[str] = field(default_factory=list)


_AI_METADATA_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "thumbnail_text": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "description", "thumbnail_text", "hashtags"],
        "additionalProperties": False,
    },
}

# Tuned via real, direct A/B calls against this app's own live project
# scripts (not a first draft) -- the user asked for a more "giat gan"
# (sensational/clickbait) tone, then for title/description to be shorter;
# both rounds of feedback are baked into these instructions directly.
def _ai_metadata_system_prompt(language_name: str) -> str:
    return (
        "You are a viral short-form video copywriter for a storytelling channel. Your style is "
        "SENSATIONAL and CLICKBAIT-driven -- the kind that stops someone mid-scroll. Use techniques "
        "like: a shocking reveal teased but not given away, a direct accusatory or confessional voice, "
        "numbers/timeframes, an unresolved question, or a twist implied. Still must be earned by the "
        "actual script -- never invent plot details it doesn't support.\n\n"
        f"Write EVERY output field entirely in {language_name}. Do not mix languages, and do not "
        "translate to any other language regardless of what language the script itself is in.\n\n"
        "BE RUTHLESSLY SHORT. Every extra word loses attention -- cut anything not essential to the hook.\n\n"
        "Given the full narration script below, write:\n"
        "- title: max 40 characters (hard limit). One sharp hook -- a confession, a turning point, or a "
        "question. No sub-clauses, no dashes with extra clarification.\n"
        "- description: max 120 characters (hard limit), ONE punchy sentence amplifying the emotional "
        "stakes, then 3 relevant hashtags on the same or next line.\n"
        "- thumbnail_text: max 5 words / 40 characters, ALL CAPS, the single most shocking/emotional "
        "line possible for a thumbnail -- must NOT just copy the title verbatim.\n"
        "- hashtags: 4 to 6 SHORT hashtags, each 1-2 words, no spaces, real searchable tags a viewer "
        "would use (e.g. #Agincourt #MedievalHistory #MilitaryHistory). Never a whole phrase or "
        "sentence as one tag.\n\n"
        "Return structured JSON only."
    )

_AI_METADATA_MAX_TOKENS = 400


def _generate_ai_metadata(script_text: str, language: str, settings: Settings) -> AIMetadata | None:
    """Never raises -- a billed AI call going wrong (no credentials
    configured, timeout, provider error, safety refusal, malformed JSON)
    must fall back to the deterministic title/description/headline, not
    hard-fail the whole Package stage (same "soft failure" precedent as
    select_thumbnail_frame's own candidate-rejection fallback).
    """
    credentials = resolve_ai_credentials(settings)
    if credentials is None or not script_text.strip():
        return None
    language_name = _LANGUAGE_NAMES.get(language, "English")
    try:
        with ai_generation_semaphore:
            result = call_structured(
                credentials, system=_ai_metadata_system_prompt(language_name),
                user_message=script_text.strip(),
                output_schema=_AI_METADATA_SCHEMA, max_tokens=_AI_METADATA_MAX_TOKENS,
                schema_name="package_ai_metadata",
            )
    except (AIProviderTimeoutError, AIProviderError) as exc:
        logger.warning("Package AI metadata call failed (%s): %s", credentials.provider, exc)
        return None
    if result.refused or not result.text:
        return None
    try:
        parsed = json.loads(result.text)
        title = str(parsed["title"]).strip()
        description = str(parsed["description"]).strip()
        thumbnail_text = str(parsed["thumbnail_text"]).strip()
        hashtags = [str(t).strip() for t in parsed.get("hashtags", []) if str(t).strip()]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Package AI metadata call returned malformed JSON: %s", exc)
        return None
    if not title or not description or not thumbnail_text:
        return None
    return AIMetadata(title=title, description=description, thumbnail_text=thumbnail_text, hashtags=hashtags)


def _ai_metadata_fingerprint(script_text: str, language: str) -> str:
    return hashlib.sha256(
        "|".join([script_text or "", language or "", AI_METADATA_ENGINE_VERSION]).encode("utf-8")
    ).hexdigest()


def _resolve_ai_metadata(job: VideoComposeJob, draft: ProjectOut, settings: Settings) -> tuple[AIMetadata | None, str | None]:
    """Reuses a cached result keyed on the project's own script text so an
    already-billed call is never repeated for unchanged content -- only a
    real script edit, a fresh opt-in, or an explicit regenerate call with
    no valid cache triggers a new one. A failed call is never cached (so
    it retries next time rather than sticking with "no AI text" forever).
    Returns (ai_metadata_or_None, fingerprint_to_persist_or_None).
    """
    if not draft.config.package.ai_metadata_enabled:
        return None, None
    script_text = draft.script_text or ""
    language = draft.config.content.language
    fingerprint = _ai_metadata_fingerprint(script_text, language)
    cache = _load_cache(job) or {}
    if cache.get("ai_metadata_fingerprint") == fingerprint and cache.get("ai_metadata"):
        return AIMetadata(**cache["ai_metadata"]), fingerprint
    ai_metadata = _generate_ai_metadata(script_text, language, settings)
    if ai_metadata is None:
        return None, None
    return ai_metadata, fingerprint


def _resolve_title_text(inputs: ContentInputs, manual_title: str | None, ai_title: str | None, max_chars: int) -> str:
    """Priority: manual (section 48) > AI-opt-in > deterministic template.
    AI text that fails validation (too long/illegal chars) silently falls
    through to the deterministic tier rather than raising -- a billed AI
    response quirk must never be the reason this stage hard-fails.
    """
    if manual_title is not None and manual_title.strip():
        return derive_title(inputs, manual_title, max_chars)
    if ai_title:
        try:
            return derive_title(inputs, ai_title, max_chars)
        except MetadataError:
            pass
    return derive_title(inputs, None, max_chars)


def _resolve_description_text(
    inputs: ContentInputs, manual_description: str | None, ai_description: str | None,
    hashtags: list[str], *, cta_enabled: bool, max_chars: int,
) -> str:
    if manual_description is not None and manual_description.strip():
        return derive_description(inputs, manual_description, hashtags, cta_enabled=cta_enabled, max_chars=max_chars)
    if ai_description:
        try:
            return derive_description(inputs, ai_description, hashtags, cta_enabled=cta_enabled, max_chars=max_chars)
        except MetadataError:
            pass
    return derive_description(inputs, None, hashtags, cta_enabled=cta_enabled, max_chars=max_chars)


def _thumbnail_config(draft: ProjectOut, width: int, height: int, headline_text: str | None) -> ThumbnailConfig:
    package_config: PackageProjectConfig = draft.config.package
    count = max(1, package_config.thumbnail_candidate_count)
    if count == 1:
        offsets = (0.5,)
    else:
        span = 0.92 - 0.08
        offsets = tuple(round(0.08 + i * span / (count - 1), 4) for i in range(count))
    return ThumbnailConfig(
        width=width, height=height, candidate_offsets=offsets,
        headline_enabled=package_config.thumbnail_headline_enabled, headline_text=headline_text,
    )


# -- Fingerprints (section 39/40) ------------------------------------------


def thumbnail_fingerprint(video_path: Path, config: ThumbnailConfig) -> str:
    stat = video_path.stat()
    payload = "|".join([
        str(video_path), str(stat.st_mtime_ns), str(stat.st_size),
        str(config.width), str(config.height), ",".join(f"{o:.4f}" for o in config.candidate_offsets),
        str(config.headline_enabled), config.headline_text or "", str(config.headline_max_chars),
        THUMBNAIL_ENGINE_VERSION,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def metadata_fingerprint(
    inputs: ContentInputs, manual_title: str | None, manual_description: str | None,
    manual_hashtags: list[str] | None, package_config: PackageProjectConfig, language: str,
    duration: float, width: int, height: int, ai_metadata: AIMetadata | None,
) -> str:
    # ai_metadata's own content (not just whether it's enabled) must be
    # part of this hash -- unlike every other input here, it is NOT a pure
    # function of `inputs`, so two calls with identical `inputs` but a
    # freshly (re)generated AI title/description must not collide.
    payload = "|".join([
        str(asdict(inputs)), manual_title or "", manual_description or "", ",".join(manual_hashtags or []),
        str(package_config.max_hashtags), package_config.platform_profile, language,
        f"{duration:.3f}", str(width), str(height), METADATA_ENGINE_VERSION,
        str(package_config.ai_metadata_enabled), str(asdict(ai_metadata)) if ai_metadata else "",
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# -- Aspect ratio label (section 10) ---------------------------------------


def _aspect_ratio_label(width: int, height: int) -> str:
    import math

    divisor = math.gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"


# -- Thumbnail generation (section 4-19) -----------------------------------


def _generate_thumbnail(job: VideoComposeJob, config: ThumbnailConfig) -> None:
    video_path = Path(job.output_path)
    work_dir = _output_dir(job) / ".thumbnail_candidates"
    try:
        best_frame = select_thumbnail_frame(video_path, config, work_dir)
        image = build_thumbnail(best_frame, config)
        out_path = thumbnail_path(job)
        tmp_path = out_path.with_suffix(".tmp.jpg")
        save_thumbnail(image, tmp_path)
        validate_thumbnail(tmp_path, expected_width=config.width, expected_height=config.height)
        tmp_path.replace(out_path)
    finally:
        import shutil

        shutil.rmtree(work_dir, ignore_errors=True)


# -- Metadata generation (section 20-30) -----------------------------------


def _generate_metadata(
    job: VideoComposeJob, draft: ProjectOut, inputs: ContentInputs, render_duration: float, width: int, height: int,
    ai_metadata: AIMetadata | None,
) -> PackageMetadata:
    package_config: PackageProjectConfig = draft.config.package
    # Manual hashtags always win. Otherwise prefer the AI's own short tags
    # (when AI metadata is on) over derive_hashtags(), which CamelCases
    # ContentBrief's full-sentence topic/angle/emotion/tone into unusable
    # monster tags -- see docs/features/126-...
    if draft.manual_hashtags is not None:
        hashtags = derive_hashtags(inputs, draft.manual_hashtags, package_config.max_hashtags)
    elif ai_metadata is not None and ai_metadata.hashtags:
        hashtags = normalize_hashtags(ai_metadata.hashtags, package_config.max_hashtags)
    else:
        hashtags = derive_hashtags(inputs, None, package_config.max_hashtags)
    title = _resolve_title_text(inputs, draft.manual_title, ai_metadata.title if ai_metadata else None, max_chars=70)
    description = _resolve_description_text(
        inputs, draft.manual_description, ai_metadata.description if ai_metadata else None, hashtags,
        cta_enabled=draft.config.content.cta_enabled, max_chars=500,
    )
    metadata = PackageMetadata(
        title=title, description=description, hashtags=hashtags,
        language=draft.config.content.language, category=derive_category(inputs),
        platform_profile=package_config.platform_profile, duration=render_duration,
        width=width, height=height, aspect_ratio=_aspect_ratio_label(width, height),
        thumbnail=_THUMBNAIL_FILENAME, video=Path(job.output_path).name,
    )
    out_path = metadata_path(job)
    tmp_path = out_path.with_suffix(".tmp.json")
    tmp_path.write_text(json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(out_path)
    return metadata


# -- The stage itself (section 37/40/41/43) --------------------------------


def generate_project_package(project_id: int, settings: Settings) -> bool:
    """Idempotent, and independently so per artifact (section 40/41/49):
    the thumbnail and metadata each have their own fingerprint, so a
    description-only edit never touches thumbnail.jpg and a final-video
    change never touches metadata.json unless the content itself also
    changed. Returns whether anything was actually (re)written this call.

    Section 37: generate -> validate -> commit -- nothing under the
    canonical `thumbnail.jpg`/`metadata.json` names is ever a partial
    write (atomic tmp-then-replace for both, matching every earlier
    stage's own convention).
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return False  # Render hasn't produced a valid final video yet -- not an error

    video_path = Path(job.output_path)
    if not video_path.exists():
        return False  # Project.render_job_id/job row exist but the file itself is gone -- reconciliation's job, not a hard failure here

    inputs = build_content_inputs(draft)
    render_meta = _read_render_metadata(job)
    duration = float(render_meta.get("duration") or 0.0)
    width = int(render_meta.get("width") or get_render_profile(draft.config.render.profile).width)
    height = int(render_meta.get("height") or get_render_profile(draft.config.render.profile).height)

    ai_metadata, ai_metadata_fp = _resolve_ai_metadata(job, draft, settings)

    # Section 14's "thumbnail headline and metadata title are the SAME
    # message" only holds for the deterministic path. AI Metadata (opt-in)
    # deliberately writes a separate, punchier thumbnail_text instead --
    # real user report that the shared-text headline felt repetitive once
    # a dedicated hook line existed. A manual title override still wins
    # over both (section 48's own "manual edits override generated
    # values").
    try:
        title_for_headline = _resolve_title_text(inputs, draft.manual_title, None, max_chars=70)
    except MetadataError:
        title_for_headline = None
    manual_title_set = draft.manual_title is not None and draft.manual_title.strip()
    if not manual_title_set and ai_metadata is not None:
        headline_text = shorten_headline(ai_metadata.thumbnail_text, 40)
    else:
        headline_text = shorten_headline(title_for_headline, 40) if title_for_headline else None

    thumb_config = _thumbnail_config(draft, width, height, headline_text)
    thumb_fp = thumbnail_fingerprint(video_path, thumb_config)
    meta_fp = metadata_fingerprint(
        inputs, draft.manual_title, draft.manual_description, draft.manual_hashtags,
        draft.config.package, draft.config.content.language, duration, width, height, ai_metadata,
    )

    cache = _load_cache(job)
    thumb_valid = thumbnail_path(job).exists()
    meta_valid = metadata_path(job).exists()
    thumb_cached = bool(cache) and cache.get("thumbnail_fingerprint") == thumb_fp and thumb_valid
    meta_cached = bool(cache) and cache.get("metadata_fingerprint") == meta_fp and meta_valid

    if thumb_cached and meta_cached:
        return False  # section 40: nothing changed, both artifacts already valid and current

    changed = False
    if not thumb_cached:
        try:
            _generate_thumbnail(job, thumb_config)
        except ThumbnailError:
            raise
        changed = True
    if not meta_cached:
        try:
            _generate_metadata(job, draft, inputs, duration, width, height, ai_metadata)
        except MetadataError:
            raise
        changed = True

    cache_fields = dict(thumbnail_fingerprint=thumb_fp, metadata_fingerprint=meta_fp, engine_version=METADATA_ENGINE_VERSION)
    if ai_metadata is not None and ai_metadata_fp is not None:
        # Persisted so a re-run with an unchanged script reuses this
        # already-billed result instead of calling the AI provider again
        # (see _resolve_ai_metadata) -- lost if some other caller
        # (e.g. regenerate-package) saves a cache without these two keys.
        cache_fields["ai_metadata_fingerprint"] = ai_metadata_fp
        cache_fields["ai_metadata"] = asdict(ai_metadata)
    _save_cache(job, **cache_fields)
    return changed


def validate_package(project_id: int, settings: Settings) -> None:
    """Section 34/43: raises PackageError(PACKAGE_INCOMPLETE) if any
    required artifact is missing, PackageError(PACKAGE_VALIDATION_FAILED)
    if one exists but fails structural validation. Never silently accepts
    a partial package.
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        raise PackageError(PACKAGE_INCOMPLETE, "No completed render exists for this project yet.")

    video_path = Path(job.output_path)
    if not video_path.exists():
        raise PackageError(PACKAGE_INCOMPLETE, f"final video is missing: {video_path}")

    thumb_path = thumbnail_path(job)
    if not thumb_path.exists():
        raise PackageError(PACKAGE_INCOMPLETE, f"thumbnail.jpg is missing: {thumb_path}")
    render_meta = _read_render_metadata(job)
    width = int(render_meta.get("width") or get_render_profile(draft.config.render.profile).width)
    height = int(render_meta.get("height") or get_render_profile(draft.config.render.profile).height)
    try:
        validate_thumbnail(thumb_path, expected_width=width, expected_height=height)
    except ThumbnailError as exc:
        raise PackageError(PACKAGE_VALIDATION_FAILED, str(exc)) from exc

    meta_path = metadata_path(job)
    if not meta_path.exists():
        raise PackageError(PACKAGE_INCOMPLETE, f"metadata.json is missing: {meta_path}")
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(PACKAGE_VALIDATION_FAILED, f"metadata.json does not parse: {exc}") from exc

    for key in ("title", "description", "hashtags"):
        if key not in data:
            raise PackageError(PACKAGE_VALIDATION_FAILED, f"metadata.json is missing required key {key!r}")
    try:
        from app.modules.metadata.service import validate_description, validate_hashtags, validate_title

        validate_title(data["title"], max_chars=200)
        validate_description(data["description"], max_chars=2000)
        validate_hashtags(data["hashtags"], max_count=max(1, len(data["hashtags"])))
    except MetadataError as exc:
        raise PackageError(PACKAGE_VALIDATION_FAILED, str(exc)) from exc


def package_is_valid(project_id: int, settings: Settings) -> bool:
    try:
        validate_package(project_id, settings)
    except PackageError:
        return False
    return True


def package_was_attempted(project_id: int, library_dir: str) -> bool:
    """Whether a prior Package stage run ever claimed to have produced
    this project's package -- mirrors every earlier stage's own
    *_was_attempted (Voice/Motion/Audio/Captions).
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return False
    return _cache_path(job).exists()


# -- API --------------------------------------------------------------------


class PackageOut(BaseModel):
    title: str | None = None
    description: str | None = None
    hashtags: list[str] = []
    language: str | None = None
    category: str | None = None
    platform_profile: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    aspect_ratio: str | None = None
    thumbnail_path: str | None = None
    video_path: str | None = None
    thumbnail_media_url: str | None = None
    video_media_url: str | None = None
    manual_title: str | None = None
    manual_description: str | None = None
    manual_hashtags: list[str] | None = None
    is_complete: bool = False


class PackageOverridesIn(BaseModel):
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    clear_title: bool = False
    clear_description: bool = False
    clear_hashtags: bool = False


def _to_media_url(file_path: str, library_dir: Path) -> str | None:
    # Duplicates video_composer.schemas._to_media_url's own tiny helper --
    # this composition root already depends on video_composer.models, but
    # that private function isn't part of this module's own contract, so
    # this 3-line transform is reproduced rather than reached into.
    try:
        rel = Path(file_path).resolve().relative_to(library_dir.resolve())
    except ValueError:
        return None
    return "/media/" + rel.as_posix()


@router.get("/projects/{project_id}/package", response_model=PackageOut)
def get_project_package(project_id: int, settings: Settings = Depends(get_settings)) -> PackageOut:
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    out = PackageOut(
        manual_title=draft.manual_title, manual_description=draft.manual_description,
        manual_hashtags=draft.manual_hashtags,
    )
    if job is None:
        return out
    library_dir = Path(settings.library_dir)
    meta_path = metadata_path(job)
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            out = out.model_copy(update={
                "title": data.get("title"), "description": data.get("description"),
                "hashtags": data.get("hashtags", []), "language": data.get("language"),
                "category": data.get("category"), "platform_profile": data.get("platform_profile"),
                "duration": data.get("duration"), "width": data.get("width"), "height": data.get("height"),
                "aspect_ratio": data.get("aspect_ratio"), "video_path": job.output_path,
                "video_media_url": _to_media_url(job.output_path, library_dir),
            })
        except (OSError, json.JSONDecodeError):
            pass
    thumb_path = thumbnail_path(job)
    if thumb_path.exists():
        out = out.model_copy(update={
            "thumbnail_path": str(thumb_path), "thumbnail_media_url": _to_media_url(str(thumb_path), library_dir),
        })
    out = out.model_copy(update={"is_complete": package_is_valid(project_id, settings)})
    return out


@router.put("/projects/{project_id}/package-overrides", response_model=dict)
def set_package_overrides(project_id: int, payload: PackageOverridesIn) -> dict:
    """Section 48: manual edits always win over the generated values.
    `clear_*` explicitly resets that field back to "derive it" -- omitting
    a field entirely leaves it untouched (see set_project_package_overrides's
    own _UNSET-sentinel reasoning).
    """
    title = None if payload.clear_title else (payload.title if payload.title is not None else _UNSET)
    description = None if payload.clear_description else (payload.description if payload.description is not None else _UNSET)
    hashtags = None if payload.clear_hashtags else (payload.hashtags if payload.hashtags is not None else _UNSET)
    set_project_package_overrides(project_id, title=title, description=description, hashtags=hashtags)
    return {"project_id": project_id}


@router.post("/projects/{project_id}/regenerate-package", response_model=dict)
def regenerate_package(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Explicit user action -- bypasses both artifacts' own cache on
    purpose, matching every earlier stage's own regenerate-* precedent.
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is not None:
        _cache_path(job).unlink(missing_ok=True)
    generated = generate_project_package(project_id, settings)
    return {"project_id": project_id, "generated": generated}


@router.post("/projects/{project_id}/regenerate-thumbnail", response_model=dict)
def regenerate_thumbnail(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Section 49: an independent action -- never reruns Script/Voice/
    Motion/Render, and (unlike regenerate-package) leaves metadata.json's
    own cache untouched if it's still valid.
    """
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return {"project_id": project_id, "generated": False}
    cache = _load_cache(job) or {}
    cache.pop("thumbnail_fingerprint", None)
    _save_cache(job, **cache)
    generated = generate_project_package(project_id, settings)
    return {"project_id": project_id, "generated": generated}


@router.post("/projects/{project_id}/regenerate-metadata", response_model=dict)
def regenerate_metadata(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    draft = get_project_draft(project_id)
    job = _completed_render_job(project_id, draft.render_job_id)
    if job is None:
        return {"project_id": project_id, "generated": False}
    cache = _load_cache(job) or {}
    cache.pop("metadata_fingerprint", None)
    _save_cache(job, **cache)
    generated = generate_project_package(project_id, settings)
    return {"project_id": project_id, "generated": generated}
