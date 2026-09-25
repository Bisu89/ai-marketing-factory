"""Manhua recap script writer (see docs/features/153-manhua-recap.md): the
model looks at a chapter's comic panels (in reading order, speech bubbles
included) and writes a fast Vietnamese recap narration, choosing which
panels to show and one short narration line per chosen panel.

Composition root, like beat_generate.py: the only place that joins
app.modules.ai (vision call) with the Beat world. Stateless -- the caller
(tools/manhua_recap/recap.py) saves the result, lets the user edit it, and
builds the project itself through the normal /projects + /beat-plan API.
Panel paths are local files on this same machine (desktop app), exactly
like POST /assets' own `path`.
"""

import io
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from PIL import Image
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import AIProviderError, LLMImage, call_structured, resolve_ai_credentials

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_PANELS = 80
MAX_TOKENS = 6000
MAX_RETRIES = 1
# Panels are downscaled before upload: wide enough to read a speech bubble,
# small enough that a 60-panel chapter stays a reasonable single request.
PANEL_MAX_WIDTH = 768
PANEL_MAX_HEIGHT = 1536
# Measured on the reference sample: ~335 Vietnamese syllables/min of
# narration (vi-VN-NamMinhNeural at speed 1.25 reads close to this).
SYLLABLES_PER_SECOND = 5.5
# The sample shows a new panel every ~2s. Real run on a 56-panel chapter:
# asked only for a syllable total, the model narrated 44 panels / 533
# syllables (~97s) against a 50s target -- so the beat count is stated
# explicitly, and a script over LENGTH_TOLERANCE x the budget is sent back
# through the repair retry.
SECONDS_PER_BEAT = 2.0
LENGTH_TOLERANCE = 1.3

LANGUAGE_NAMES = {"vi": "Vietnamese", "en": "English", "ko": "Korean"}

SYSTEM_PROMPT = (
    "You write narration for fast short-form comic recap videos. You are given the panels "
    "of ONE comic chapter in reading order, each labelled 'Panel N'. Read every panel "
    "carefully, including speech bubbles, captions and sound effects, and work out what "
    "actually happens: who the characters are, what they want, the expectation the chapter "
    "sets up, the twist, and how it ends.\n\n"
    "Then write the recap as a sequence of beats. Each beat shows exactly ONE panel on "
    "screen while one short piece of narration is read over it.\n"
    "- Panels must be used in strictly increasing order. Skip panels that are redundant, "
    "unreadable, mostly text/blank, or don't move the story, and ALWAYS skip ads, credits, "
    "translator notes and website/app promo banners; never reuse a panel.\n"
    "- Each beat's narration is one short clause or sentence (roughly 8-20 syllables) that "
    "matches what that panel shows.\n"
    "- Third person, plain spoken language, fast and punchy, lightly comedic where the "
    "chapter is funny. No greeting, no 'in this chapter', never mention panels, comics, or "
    "the reader. Do not read speech bubbles out verbatim -- retell them.\n"
    "- The very first beat is the hook: drop the viewer straight into the situation.\n"
    "- The last beat lands the chapter's ending/reaction.\n"
    "- Use the character names if the panels give them; otherwise short descriptive labels "
    "(e.g. 'lão già', 'gã kiếm tiên').\n"
    "Also return a short catchy video title (max 80 characters) in the same language."
)

OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "beats": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "panel": {"type": "integer"},
                        "narration": {"type": "string"},
                    },
                    "required": ["panel", "narration"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "beats"],
        "additionalProperties": False,
    },
}


class ManhuaScriptIn(BaseModel):
    panel_paths: list[str] = Field(min_length=3, max_length=MAX_PANELS)
    target_duration: float = Field(default=50.0, gt=5, le=600)
    language: str = "vi"
    # Free-text context the panels can't give: series name, who's who,
    # "this is chapter 12, the old man is the sect master", etc.
    notes: str | None = None


class ManhuaBeatOut(BaseModel):
    panel: int  # 1-based index into panel_paths
    narration: str


class ManhuaScriptOut(BaseModel):
    title: str
    beats: list[ManhuaBeatOut]


def _load_panel(path_str: str, index: int) -> LLMImage:
    path = Path(path_str)
    if not path.is_file():
        raise ValidationError(f"Panel {index} not found: {path_str}")
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((PANEL_MAX_WIDTH, PANEL_MAX_HEIGHT))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
    except OSError as exc:
        raise ValidationError(f"Panel {index} is not a readable image: {path_str}") from exc
    return LLMImage(media_type="image/jpeg", data=buf.getvalue(), label=f"Panel {index}")


def _build_user_message(payload: ManhuaScriptIn) -> str:
    language = LANGUAGE_NAMES.get(payload.language, payload.language)
    syllables = _syllable_budget(payload.target_duration)
    beats = max(3, round(payload.target_duration / SECONDS_PER_BEAT))
    lines = [
        f"There are {len(payload.panel_paths)} panels above (Panel 1 .. Panel {len(payload.panel_paths)}).",
        f"Write the recap in {language}.",
        f"Target length: about {payload.target_duration:.0f} seconds read fast -- about {beats} beats and "
        f"roughly {syllables} words/syllables of narration in total (hard maximum "
        f"{round(syllables * LENGTH_TOLERANCE)}). You will NOT use every panel: pick the ~{beats} that tell "
        "the story best and compress -- this is a recap, not a retelling.",
    ]
    if payload.notes:
        lines.append(f"Context from the channel owner: {payload.notes}")
    return "\n".join(lines)


def _syllable_budget(target_duration: float) -> int:
    return round(target_duration * SYLLABLES_PER_SECOND)


def _validate(parsed: dict, panel_count: int, syllable_budget: int) -> ManhuaScriptOut:
    out = ManhuaScriptOut.model_validate(parsed)
    if len(out.beats) < 3:
        raise ValueError(f"only {len(out.beats)} beats returned, need at least 3")
    previous = 0
    for beat in out.beats:
        if not 1 <= beat.panel <= panel_count:
            raise ValueError(f"panel {beat.panel} is out of range 1..{panel_count}")
        if beat.panel <= previous:
            raise ValueError(f"panels must be strictly increasing, got {beat.panel} after {previous}")
        if not beat.narration.strip():
            raise ValueError(f"beat for panel {beat.panel} has empty narration")
        previous = beat.panel
    total = sum(len(beat.narration.split()) for beat in out.beats)
    if total > syllable_budget * LENGTH_TOLERANCE:
        raise ValueError(
            f"narration is {total} words/syllables, over the maximum of "
            f"{round(syllable_budget * LENGTH_TOLERANCE)} -- use fewer beats and shorter lines"
        )
    out.title = out.title.strip()[:100] or "Manhua recap"
    return out


def generate_manhua_script(settings: Settings, payload: ManhuaScriptIn) -> ManhuaScriptOut:
    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise ValidationError("No AI provider is configured. Go to Settings to choose a provider and enter an API key.")

    images = [_load_panel(p, i) for i, p in enumerate(payload.panel_paths, 1)]
    user_message = _build_user_message(payload)

    repair_note: str | None = None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        system = SYSTEM_PROMPT
        if repair_note:
            system += f"\n\nYour previous response was invalid: {repair_note}\nFix it and return valid JSON only."
        try:
            result = call_structured(
                credentials, system=system, user_message=user_message, output_schema=OUTPUT_SCHEMA,
                max_tokens=MAX_TOKENS, schema_name="manhua_recap", images=images,
            )
        except AIProviderError as exc:
            raise ExternalServiceError(f"AI provider call failed: {exc}") from exc
        if result.refused:
            raise ExternalServiceError("Request was refused by the model's safety filter.")
        if not result.text:
            raise ExternalServiceError("Model did not return any text content.")
        try:
            return _validate(json.loads(result.text), len(images), _syllable_budget(payload.target_duration))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Manhua script attempt %d/%d invalid: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
            repair_note = str(exc)

    raise ExternalServiceError(f"Could not write a valid recap after {MAX_RETRIES + 1} attempts: {last_error}")


@router.post("/manhua-recap/script", response_model=ManhuaScriptOut)
def create_manhua_script(payload: ManhuaScriptIn, settings: Settings = Depends(get_settings)) -> ManhuaScriptOut:
    return generate_manhua_script(settings, payload)
