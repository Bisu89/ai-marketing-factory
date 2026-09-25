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
# Real render (project 112): vi-VN-NamMinhNeural at speed 1.6 read 262
# syllables in 51.1s = ~5.1/s (~308/min; the reference sample is ~335/min).
# At 1.25 it was only ~4.0/s -- a "50s" script rendered at 65s.
SYLLABLES_PER_SECOND = 5.1
# The sample shows a new panel every ~2s. Real run on a 56-panel chapter:
# asked only for a syllable total, the model narrated 44 panels / 533
# syllables (~97s) against a 50s target -- so the beat count is stated
# explicitly, and a script over LENGTH_TOLERANCE x the budget is sent back
# through the repair retry.
SECONDS_PER_BEAT = 2.0
LENGTH_TOLERANCE = 1.3

BEAT_TYPES = ("HOOK", "SETUP", "BUILD", "REVEAL", "REACTION", "ENDING")
# YouTube's monetization policy (reused content, updated 2025-07) rejects
# videos that only re-read someone else's material, but allows "edited
# footage ... where you add a storyline and commentary" and critical review.
# So by default a recap must carry the channel's own take: "commentary"
# beats (opinion, analysis, prediction) next to the plain "recap" beats,
# checked below rather than left to the prompt alone.
BEAT_KINDS = ("recap", "commentary")
MIN_COMMENTARY_BEATS = 2
MIN_COMMENTARY_SHARE = 0.15  # of total narration syllables

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
    "- The recap lands the chapter's ending/reaction.\n"
    "- Use the character names if the panels give them; otherwise short descriptive labels "
    "(e.g. 'lão già', 'gã kiếm tiên').\n"
    "- Give each beat a `type` for its role: HOOK (first beat only), SETUP, BUILD, REVEAL "
    "(a twist/secret comes out), REACTION (someone's shock/response), ENDING (last beat only). "
    "Vary them the way the story actually moves -- not a long run of BUILD.\n"
    "- Mark every beat's `kind` as \"recap\" (retelling what happens).\n"
    "Also return a short catchy video title (max 80 characters) in the same language."
)

# Appended when commentary is on; overrides the plain-recap ending/kind rules above.
COMMENTARY_RULES = (
    "\n\nCOMMENTARY -- this channel is a REVIEW channel, not a read-along. Besides the recap "
    "beats, write beats of the channel host's own take, marked `kind`: \"commentary\":\n"
    "- Spoken by the host in first person (Vietnamese: 'mình'), casual and confident.\n"
    "- Specific to THIS chapter, never generic praise ('hay quá', 'đỉnh thật' alone is not "
    "commentary): why a move or reveal is clever, what it says about a character's real power "
    "or personality, a detail most readers miss, how it sets something up, a prediction for "
    "the next chapter.\n"
    "- Put 1-2 short commentary beats in the middle, right after the moment they react to, "
    "and END the video with 2-3 commentary beats: the host's verdict on the chapter, then a "
    "prediction or a question for viewers as the very last line. The recap's own climax comes "
    "just before that closing take.\n"
    "- A commentary beat still shows one panel (still strictly increasing): pick one that "
    "fits what is being said.\n"
    "- Commentary is part of the same length budget -- compress the recap to make room, "
    "roughly 20-30% of all narration should be commentary.\n"
    "- The last beat's `type` is ENDING even though it is commentary."
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
                        "type": {"type": "string", "enum": list(BEAT_TYPES)},
                        "kind": {"type": "string", "enum": list(BEAT_KINDS)},
                        "narration": {"type": "string"},
                    },
                    "required": ["panel", "type", "kind", "narration"],
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
    # Host commentary beats (see BEAT_KINDS). False = plain recap only.
    commentary: bool = True


class ManhuaBeatOut(BaseModel):
    panel: int  # 1-based index into panel_paths
    type: str = "BUILD"  # one of BEAT_TYPES -- becomes Beat.type on the built project
    kind: str = "recap"  # one of BEAT_KINDS
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
    if payload.commentary:
        # First real run with commentary overshot the maximum even after the
        # repair retry: the model added the host's take ON TOP of a full-length
        # recap. Spell out the split so the recap is compressed up front.
        commentary_beats = max(MIN_COMMENTARY_BEATS + 1, round(beats * 0.25))
        lines.append(
            f"Split that budget: about {beats - commentary_beats} recap beats (~{round(syllables * 0.75)} "
            f"syllables) and about {commentary_beats} commentary beats (~{round(syllables * 0.25)} syllables). "
            "The recap must be SHORTER than a plain recap would be -- the host's take replaces story detail, "
            "it is not added on top."
        )
    if payload.notes:
        lines.append(f"Context from the channel owner: {payload.notes}")
    return "\n".join(lines)


def _syllable_budget(target_duration: float) -> int:
    return round(target_duration * SYLLABLES_PER_SECOND)


def _check_commentary(beats: list[ManhuaBeatOut]) -> None:
    commentary = [b for b in beats if b.kind == "commentary"]
    if len(commentary) < MIN_COMMENTARY_BEATS:
        raise ValueError(
            f"only {len(commentary)} commentary beat(s), need at least {MIN_COMMENTARY_BEATS} "
            "(1-2 in the middle and a closing take)"
        )
    if beats[-1].kind != "commentary":
        raise ValueError("the last beat must be the host's commentary (verdict / prediction / question)")
    total = sum(len(b.narration.split()) for b in beats)
    share = sum(len(b.narration.split()) for b in commentary) / max(total, 1)
    if share < MIN_COMMENTARY_SHARE:
        raise ValueError(
            f"commentary is only {share:.0%} of the narration, need at least {MIN_COMMENTARY_SHARE:.0%} "
            "-- compress the recap and give the host more of their own take"
        )


def _validate(
    parsed: dict, panel_count: int, syllable_budget: int, commentary: bool = True,
) -> ManhuaScriptOut:
    out = ManhuaScriptOut.model_validate(parsed)
    if len(out.beats) < 3:
        raise ValueError(f"only {len(out.beats)} beats returned, need at least 3")
    previous = 0
    for beat in out.beats:
        if not 1 <= beat.panel <= panel_count:
            raise ValueError(f"panel {beat.panel} is out of range 1..{panel_count}")
        if beat.panel <= previous:
            raise ValueError(f"panels must be strictly increasing, got {beat.panel} after {previous}")
        if beat.type not in BEAT_TYPES:
            raise ValueError(f"beat for panel {beat.panel} has unknown type {beat.type!r}")
        if beat.kind not in BEAT_KINDS:
            raise ValueError(f"beat for panel {beat.panel} has unknown kind {beat.kind!r}")
        if not beat.narration.strip():
            raise ValueError(f"beat for panel {beat.panel} has empty narration")
        previous = beat.panel
    total = sum(len(beat.narration.split()) for beat in out.beats)
    if total > syllable_budget * LENGTH_TOLERANCE:
        raise ValueError(
            f"narration is {total} words/syllables, over the maximum of "
            f"{round(syllable_budget * LENGTH_TOLERANCE)} -- use fewer beats and shorter lines"
        )
    if commentary:
        _check_commentary(out.beats)
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
        system = SYSTEM_PROMPT + (COMMENTARY_RULES if payload.commentary else "")
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
            return _validate(
                json.loads(result.text), len(images), _syllable_budget(payload.target_duration), payload.commentary,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Manhua script attempt %d/%d invalid: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
            repair_note = str(exc)

    raise ExternalServiceError(f"Could not write a valid recap after {MAX_RETRIES + 1} attempts: {last_error}")


@router.post("/manhua-recap/script", response_model=ManhuaScriptOut)
def create_manhua_script(payload: ManhuaScriptIn, settings: Settings = Depends(get_settings)) -> ManhuaScriptOut:
    return generate_manhua_script(settings, payload)
