"""The Story planning pipeline's per-stage worker functions (plan Phase 4),
extracted from story_pipeline.py the same way factory_stages.py was
extracted from factory_pipeline.py -- so the orchestrator stays a thin
loop and each stage is independently testable.

Every LLM stage:
  1. is idempotent -- a story that already has the stage's output (a
     premise, characters, chapters, a chapter's scenes) is left untouched
     (`reuse, don't regenerate`, exactly like factory_stages._stage_generate_beats),
  2. routes its call through app.modules.ai.model_router (task_kind -> tier
     -> token headroom, and a real model id once TIER_MODEL_MAP is filled),
  3. validates the model output BEFORE persisting anything,
  4. raises StoryStageError(stage, code, message) on any real failure --
     caught once, in the orchestrator, and turned into
     StoryRun.failed_stage / error_code / error_message.

No APIRouter here -- these are called, never routed.
"""

from __future__ import annotations

import json
import logging

from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings
from app.modules.ai.llm_client import (
    AICredentials,
    AIProviderError,
    AIProviderTimeoutError,
    call_structured,
    resolve_ai_credentials,
)
from app.modules.ai.model_router import route
from app.modules.story import service
from app.modules.story.models import SCENE_TYPES

logger = logging.getLogger(__name__)

# Stage -> user-facing error code (StoryRunOut.error_code). Stable strings
# the frontend can switch on, never a raw exception message.
STORY_DEVELOPMENT_FAILED = "STORY_DEVELOPMENT_FAILED"
STORY_BIBLE_FAILED = "STORY_BIBLE_FAILED"
CHARACTER_BIBLE_FAILED = "CHARACTER_BIBLE_FAILED"
CHAPTER_OUTLINE_FAILED = "CHAPTER_OUTLINE_FAILED"
SCENE_BREAKDOWN_FAILED = "SCENE_BREAKDOWN_FAILED"
AI_NOT_CONFIGURED = "AI_NOT_CONFIGURED"
AI_PROVIDER_TIMEOUT = "AI_PROVIDER_TIMEOUT"
AI_REFUSED = "AI_REFUSED"
MALFORMED_AI_RESPONSE = "MALFORMED_AI_RESPONSE"

_MODE_FRAMING = {
    "STORY": "an original fictional short-story / cinematic narrative",
    "HISTORY": "a factual history documentary (report only what the reference notes support -- invent nothing)",
    "EDUCATION": "an educational explainer (accurate, structured, no invented facts)",
}


class StoryStageError(Exception):
    def __init__(self, stage: str, code: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.message = message


# -- shared LLM call -----------------------------------------------------


def _llm_json(
    credentials: AICredentials,
    *,
    stage: str,
    task_kind: str,
    system: str,
    user: str,
    schema: dict,
    base_max_tokens: int,
    fail_code: str,
) -> dict:
    """One routed, structured-output call -> parsed JSON dict. Translates
    every provider failure into a StoryStageError for `stage`.
    """
    decision = route(task_kind, credentials.provider)
    logger.info("story stage %s: %s", stage, decision.note)
    try:
        with ai_generation_semaphore:
            result = call_structured(
                credentials,
                system=system,
                user_message=user,
                output_schema={"type": "json_schema", "schema": schema},
                max_tokens=base_max_tokens + decision.max_tokens_bonus,
                schema_name=task_kind,
                model=decision.model,
            )
    except AIProviderTimeoutError as exc:
        raise StoryStageError(stage, AI_PROVIDER_TIMEOUT, f"The AI provider timed out: {exc}") from exc
    except AIProviderError as exc:
        raise StoryStageError(stage, fail_code, f"The AI provider call failed: {exc}") from exc
    if result.refused:
        raise StoryStageError(stage, AI_REFUSED, "The model refused this request.")
    if not (result.text or "").strip():
        raise StoryStageError(stage, MALFORMED_AI_RESPONSE, "The model returned no text.")
    try:
        return json.loads(result.text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise StoryStageError(stage, MALFORMED_AI_RESPONSE, f"The model returned malformed JSON: {exc}") from exc


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def _arr(items: dict) -> dict:
    return {"type": "array", "items": items}


def _resolve_credentials(settings: Settings, stage: str) -> AICredentials:
    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise StoryStageError(
            stage, AI_NOT_CONFIGURED,
            "No AI provider is configured. Go to Settings to choose a provider and enter an API key.",
        )
    return credentials


def _story_header(story) -> str:
    bits = [f"Title: {story.title}", f"Mode: {story.mode}"]
    if story.logline:
        bits.append(f"Logline: {story.logline}")
    if story.genre:
        bits.append(f"Genre: {story.genre}")
    return "\n".join(bits)


# -- Stage: STORY_DEVELOPMENT -------------------------------------------

_DEVELOPMENT_SCHEMA = _obj(
    {
        "premise": {"type": "string"},
        "synopsis": {"type": "string"},
        "central_conflict": {"type": "string"},
        "tone": {"type": "string"},
        "setting_summary": {"type": "string"},
        "themes": _arr({"type": "string"}),
    },
    ["premise", "synopsis", "central_conflict", "tone", "setting_summary", "themes"],
)


def generate_story_development(credentials: AICredentials, story) -> dict:
    framing = _MODE_FRAMING.get(story.mode, _MODE_FRAMING["STORY"])
    system = (
        f"You are a development editor shaping {framing}. Produce a tight, production-ready "
        "premise for a short-form video. Return JSON only, matching the schema."
    )
    user = _story_header(story)
    if story.reference_notes:
        user += f"\n\nReference notes (the ONLY source for factual claims):\n{story.reference_notes}"
    return _llm_json(
        credentials, stage="STORY_DEVELOPMENT", task_kind="story_development",
        system=system, user=user, schema=_DEVELOPMENT_SCHEMA,
        base_max_tokens=1500, fail_code=STORY_DEVELOPMENT_FAILED,
    )


def _stage_story_development(story_id: int, settings: Settings) -> bool:
    story = service.get_story(story_id)
    if (story.story_bible_json or {}).get("premise"):
        return False
    credentials = _resolve_credentials(settings, "STORY_DEVELOPMENT")
    data = generate_story_development(credentials, story)
    service.merge_story_json(story_id, story_bible={
        "premise": data["premise"],
        "synopsis": data["synopsis"],
        "central_conflict": data["central_conflict"],
        "tone": data["tone"],
        "setting_summary": data["setting_summary"],
        "themes": data.get("themes", []),
    })
    return True


# -- Stage: STORY_BIBLE ------------------------------------------------

_BIBLE_SCHEMA = _obj(
    {
        "world_rules": _arr({"type": "string"}),
        "timeline": _arr({"type": "string"}),
        "locations": _arr(_obj(
            {"name": {"type": "string"}, "description": {"type": "string"}, "mood": {"type": "string"}},
            ["name", "description", "mood"],
        )),
        "style": _obj(
            {
                "palette": {"type": "string"},
                "lighting": {"type": "string"},
                "mood": {"type": "string"},
                "visual_references": _arr({"type": "string"}),
            },
            ["palette", "lighting", "mood", "visual_references"],
        ),
    },
    ["world_rules", "timeline", "locations", "style"],
)


def generate_story_bible(credentials: AICredentials, story) -> dict:
    system = (
        "You are a story bible author. Given the premise below, define the world rules, a short "
        "beat-level timeline, the key locations, and a consistent visual style. Return JSON only."
    )
    bible = story.story_bible_json or {}
    user = (
        _story_header(story)
        + f"\n\nPremise: {bible.get('premise', '')}"
        + f"\nSynopsis: {bible.get('synopsis', '')}"
        + f"\nCentral conflict: {bible.get('central_conflict', '')}"
    )
    return _llm_json(
        credentials, stage="STORY_BIBLE", task_kind="story_bible",
        system=system, user=user, schema=_BIBLE_SCHEMA,
        base_max_tokens=2200, fail_code=STORY_BIBLE_FAILED,
    )


def _stage_story_bible(story_id: int, settings: Settings) -> bool:
    story = service.get_story(story_id)
    if (story.story_bible_json or {}).get("world_rules"):
        return False
    credentials = _resolve_credentials(settings, "STORY_BIBLE")
    data = generate_story_bible(credentials, story)
    service.merge_story_json(
        story_id,
        story_bible={"world_rules": data["world_rules"], "timeline": data["timeline"]},
        style_bible=data["style"],
    )
    # Locations become real rows (only if none exist yet).
    if not service.list_locations(story_id):
        for loc in data.get("locations", []):
            service.add_location(
                story_id, name=loc["name"][:200], description=loc.get("description"), mood=loc.get("mood"),
            )
    return True


# -- Stage: CHARACTER_BIBLE ------------------------------------------

_CHARACTER_SCHEMA = _obj(
    {"characters": _arr(_obj(
        {
            "name": {"type": "string"},
            "role": {"type": "string"},
            "age": {"type": "string"},
            "gender": {"type": "string"},
            "appearance": {"type": "string"},
            "wardrobe": {"type": "string"},
            "personality": {"type": "string"},
            "canonical_prompt_block": {"type": "string"},
            "negative_constraints": {"type": "string"},
        },
        ["name", "role", "age", "gender", "appearance", "wardrobe", "personality",
         "canonical_prompt_block", "negative_constraints"],
    ))},
    ["characters"],
)


def generate_character_bible(credentials: AICredentials, story) -> dict:
    system = (
        "You are a character designer. Produce every named character the story needs, each with a "
        "LOCKED `canonical_prompt_block` -- one dense visual description (face, hair, build, wardrobe) "
        "that will be reused verbatim in every image prompt so the character never drifts. Return JSON only."
    )
    bible = story.story_bible_json or {}
    user = _story_header(story) + f"\n\nSynopsis: {bible.get('synopsis', '')}\nTone: {bible.get('tone', '')}"
    return _llm_json(
        credentials, stage="CHARACTER_BIBLE", task_kind="character_bible",
        system=system, user=user, schema=_CHARACTER_SCHEMA,
        base_max_tokens=2200, fail_code=CHARACTER_BIBLE_FAILED,
    )


def _stage_character_bible(story_id: int, settings: Settings) -> bool:
    if service.list_characters(story_id):
        return False
    story = service.get_story(story_id)
    credentials = _resolve_credentials(settings, "CHARACTER_BIBLE")
    data = generate_character_bible(credentials, story)
    rows = [
        {
            "name": c["name"][:200],
            "role": c.get("role"),
            "age": c.get("age"),
            "gender": c.get("gender"),
            "appearance": c.get("appearance"),
            "wardrobe": c.get("wardrobe"),
            "personality": c.get("personality"),
            "canonical_prompt_block": c.get("canonical_prompt_block"),
            "negative_constraints": c.get("negative_constraints"),
        }
        for c in data.get("characters", [])
    ]
    if not rows:
        raise StoryStageError("CHARACTER_BIBLE", CHARACTER_BIBLE_FAILED, "The model produced no characters.")
    service.bulk_add_characters(story_id, rows)
    return True


# -- Stage: CHAPTER_OUTLINE -----------------------------------------

_CHAPTER_SCHEMA = _obj(
    {"chapters": _arr(_obj(
        {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "goal": {"type": "string"},
            "retention_notes": {"type": "string"},
        },
        ["title", "summary", "goal", "retention_notes"],
    ))},
    ["chapters"],
)


def generate_chapter_outline(credentials: AICredentials, story) -> dict:
    system = (
        "You are a story structure editor. Break the story into ordered chapters (segments). Each chapter "
        "has a clear dramatic goal and a retention note (why the viewer keeps watching into the next one). "
        "Return JSON only, chapters in narrative order."
    )
    bible = story.story_bible_json or {}
    user = (
        _story_header(story)
        + f"\n\nSynopsis: {bible.get('synopsis', '')}"
        + f"\nCentral conflict: {bible.get('central_conflict', '')}"
        + f"\nTimeline: {'; '.join(bible.get('timeline', []))}"
    )
    return _llm_json(
        credentials, stage="CHAPTER_OUTLINE", task_kind="chapter_outline",
        system=system, user=user, schema=_CHAPTER_SCHEMA,
        base_max_tokens=1800, fail_code=CHAPTER_OUTLINE_FAILED,
    )


def _stage_chapter_outline(story_id: int, settings: Settings) -> bool:
    if service.list_chapters(story_id):
        return False
    story = service.get_story(story_id)
    credentials = _resolve_credentials(settings, "CHAPTER_OUTLINE")
    data = generate_chapter_outline(credentials, story)
    rows = [
        {
            "order": i,
            "title": c.get("title", f"Chapter {i}")[:200],
            "summary": c.get("summary"),
            "goal": c.get("goal"),
            "retention_notes": c.get("retention_notes"),
        }
        for i, c in enumerate(data.get("chapters", []), start=1)
    ]
    if not rows:
        raise StoryStageError("CHAPTER_OUTLINE", CHAPTER_OUTLINE_FAILED, "The model produced no chapters.")
    service.bulk_add_chapters(story_id, rows)
    return True


# -- Stage: SCENE_BREAKDOWN ----------------------------------------

_SCENE_SCHEMA = _obj(
    {"scenes": _arr(_obj(
        {
            "scene_type": {"type": "string", "enum": list(SCENE_TYPES)},
            "narration": {"type": "string"},
            "dialogue": _arr(_obj(
                {"character_name": {"type": "string"}, "line": {"type": "string"}},
                ["character_name", "line"],
            )),
            "character_names": _arr({"type": "string"}),
            "location_name": {"type": "string"},
            "camera": {"type": "string"},
            "emotion": {"type": "string"},
            "time_of_day": {"type": "string"},
            "duration_hint": {"type": "number"},
        },
        ["scene_type", "narration", "dialogue", "character_names", "location_name",
         "camera", "emotion", "time_of_day", "duration_hint"],
    ))},
    ["scenes"],
)


def generate_scene_breakdown(credentials: AICredentials, story, chapter, characters: list, locations: list) -> dict:
    cast = ", ".join(c.name for c in characters) or "(none defined)"
    locs = ", ".join(loc.name for loc in locations) or "(none defined)"
    system = (
        "You are a scene writer for an audio-first short video. Break this ONE chapter into ordered scenes. "
        "Each scene: one narration paragraph (what is spoken), optional dialogue lines, which characters are "
        "on screen, the location, a camera note, the dominant emotion, and a duration_hint in seconds "
        "(3-12). Use ONLY the cast and locations listed. Return JSON only, scenes in order."
    )
    user = (
        _story_header(story)
        + f"\n\nCast: {cast}\nLocations: {locs}"
        + f"\n\nChapter {chapter.order}: {chapter.title or ''}\nGoal: {chapter.goal or ''}\nSummary: {chapter.summary or ''}"
    )
    return _llm_json(
        credentials, stage="SCENE_BREAKDOWN", task_kind="scene_breakdown",
        system=system, user=user, schema=_SCENE_SCHEMA,
        base_max_tokens=2600, fail_code=SCENE_BREAKDOWN_FAILED,
    )


def _clamp_duration(value) -> float:
    try:
        return max(2.0, min(20.0, float(value)))
    except (TypeError, ValueError):
        return 6.0


def _stage_scene_breakdown(story_id: int, settings: Settings) -> bool:
    story = service.get_story(story_id)
    chapters = service.list_chapters(story_id)
    if not chapters:
        raise StoryStageError("SCENE_BREAKDOWN", SCENE_BREAKDOWN_FAILED, "No chapters to break into scenes.")

    characters = service.list_characters(story_id)
    locations = service.list_locations(story_id)
    char_by_name = {c.name.strip().lower(): c.id for c in characters}
    loc_by_name = {loc.name.strip().lower(): loc.id for loc in locations}

    did_any = False
    credentials = None
    for chapter in chapters:
        if service.list_scenes(chapter.id):
            continue  # this chapter already broken down -- resume-safe
        if credentials is None:
            credentials = _resolve_credentials(settings, "SCENE_BREAKDOWN")
        data = generate_scene_breakdown(credentials, story, chapter, characters, locations)
        rows = []
        for i, sc in enumerate(data.get("scenes", []), start=1):
            names = [n.strip().lower() for n in sc.get("character_names", [])]
            char_ids = [char_by_name[n] for n in names if n in char_by_name]
            dialogue = [
                {"character_id": char_by_name[d["character_name"].strip().lower()], "line": d["line"]}
                for d in sc.get("dialogue", [])
                if d.get("character_name", "").strip().lower() in char_by_name and d.get("line")
            ]
            scene_type = sc.get("scene_type") if sc.get("scene_type") in SCENE_TYPES else "BODY"
            rows.append({
                "order": i,
                "scene_type": scene_type,
                "narration": sc.get("narration"),
                "dialogue_json": dialogue,
                "character_ids_json": char_ids,
                "location_id": loc_by_name.get(sc.get("location_name", "").strip().lower()),
                "camera": (sc.get("camera") or None),
                "emotion": (sc.get("emotion") or None),
                "time_of_day": (sc.get("time_of_day") or None),
                "duration_hint": _clamp_duration(sc.get("duration_hint")),
            })
        if not rows:
            raise StoryStageError(
                "SCENE_BREAKDOWN", SCENE_BREAKDOWN_FAILED,
                f"The model produced no scenes for chapter {chapter.order}.",
            )
        service.bulk_add_scenes(chapter.id, rows)
        did_any = True
    return did_any
