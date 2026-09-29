"""Story Remix (docs/features/155-story-remix-pipeline.md): transcribe 1-3
trending "xuyên không" (transmigration/isekai) or "hệ thống" (hidden-System)
storytelling videos and have the model rewrite them into a genuinely new,
substantially-transformed chapter for the "isekai_system_vi" built-in
template.

Composition root, like manhua_recap.py: the only place that joins
app.modules.ai (transcription + a structured rewrite call) with the Beat
world. Stateless -- the caller (tools/story_remix/remix.py) saves the
result, lets the user hand-review it, and builds the project itself
through the normal /projects + /beat-plan API, same contract
manhua_recap.py's own CLI already established.

YouTube's "reused/duplicative content" policy (updated 2025-07, see
manhua_recap.py's own BEAT_KINDS comment for the same citation) targets
exactly this pipeline's shape: take another creator's story, reword it,
republish. Per that policy, and manhua_recap.py's own precedent (a
mandatory host-commentary share, checked in code, never left to the
prompt alone), the transformation required here is a real gate, not a
request:

- The model must self-report, per response, whether it renamed every
  character, used a new setting, changed the ending, and (with 2+
  sources) blended them -- `_check_transformation` rejects any response
  that doesn't claim every required axis, feeding the miss back through
  the same bounded repair-retry loop chinese_drama_dub.py established.
- When a source and the target share a language (the common real case --
  a Vietnamese-narrated source rewritten into Vietnamese), a cheap
  word-level n-gram overlap check against that source's own transcript is
  also enforced -- the case a close paraphrase could otherwise slip
  through the self-report alone. It's intentionally NOT enforced across a
  language pair, since translation to a different language already drives
  raw lexical overlap near zero regardless of how much the plot itself
  was (or wasn't) transformed -- see `_check_same_language_overlap`.
"""

import json
import logging
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import AIProviderError, call_structured, resolve_ai_credentials
from app.modules.ai.transcribe_client import (
    TranscribeError,
    estimate_transcription_cost_usd,
    extract_audio_track,
    probe_audio_duration,
    transcribe_audio,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_SOURCES = 3
MIN_BEATS = 6
MAX_TOKENS = 4000
MAX_RETRIES = 2  # two repair attempts: JSON/beat validity, the transformation gate, and the overlap gate can each fail independently

# Word-level n-gram overlap ratio against a SAME-LANGUAGE source transcript,
# above which a draft is rejected as "too close to source N" and sent back
# through the repair loop. Chosen conservatively (a real chapter naturally
# shares some common phrasing/tropes with its genre) -- tune after real runs.
OVERLAP_NGRAM = 5
MAX_SAME_LANGUAGE_OVERLAP = 0.15

BEAT_TYPES = ("HOOK", "SETUP", "BUILD", "REVEAL", "REACTION", "ENDING")
LANGUAGE_NAMES = {"vi": "Vietnamese", "ko": "Korean", "en": "English", "zh": "Chinese"}


# -- transcription -----------------------------------------------------------


class TranscribeIn(BaseModel):
    video_path: str
    language: str = Field(description="Spoken language of the source video, e.g. 'vi', 'ko', 'zh', 'en'")


class TranscribeOut(BaseModel):
    text: str
    duration_sec: float
    cost_usd: float | None = None


@router.post("/story-remix/transcribe", response_model=TranscribeOut)
def transcribe_source(payload: TranscribeIn, settings: Settings = Depends(get_settings)) -> TranscribeOut:
    if not settings.openai_api_key:
        raise ValidationError("No OpenAI API key configured -- add one in Settings (transcription requires OpenAI).")
    video_path = Path(payload.video_path)
    if not video_path.is_file():
        raise ValidationError(f"Video not found: {payload.video_path}")

    with tempfile.TemporaryDirectory(prefix="story_remix_asr_") as tmp:
        audio_path = Path(tmp) / "audio.mp3"
        try:
            extract_audio_track(video_path, audio_path)
            duration_sec = probe_audio_duration(audio_path)
            transcription = transcribe_audio(settings.openai_api_key, audio_path, language=payload.language)
        except TranscribeError as exc:
            raise ExternalServiceError(str(exc)) from exc

    return TranscribeOut(
        text=transcription.text,
        duration_sec=duration_sec,
        cost_usd=estimate_transcription_cost_usd(duration_sec),
    )


# -- rewrite ------------------------------------------------------------------


class SourceIn(BaseModel):
    text: str
    language: str
    label: str = "source"

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source text must not be blank")
        return value


class RewriteIn(BaseModel):
    sources: list[SourceIn] = Field(min_length=1, max_length=MAX_SOURCES)
    target_language: str = "vi"
    # Free-text context the transcripts alone can't give: which trope to lean
    # into, a note about tone, anything the channel owner wants carried over.
    notes: str | None = None


class BeatOut(BaseModel):
    type: str  # one of BEAT_TYPES
    narration: str
    visual_hint: str  # short 3-10 word label, becomes Beat.visual_hint
    visual_description: str  # a real showable image description, becomes Beat.visual_description


class TransformationOut(BaseModel):
    renamed_characters: bool
    changed_setting: bool
    changed_ending: bool
    # Only meaningful with 2+ sources; with exactly one source this is
    # accepted either way (nothing to blend) -- see _check_transformation.
    blended_sources: bool


class RewriteOut(BaseModel):
    title: str
    new_setting: str
    beats: list[BeatOut]
    transformation: TransformationOut


OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "new_setting": {"type": "string"},
            "beats": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": list(BEAT_TYPES)},
                        "narration": {"type": "string"},
                        "visual_hint": {"type": "string"},
                        "visual_description": {"type": "string"},
                    },
                    "required": ["type", "narration", "visual_hint", "visual_description"],
                    "additionalProperties": False,
                },
            },
            "transformation": {
                "type": "object",
                "properties": {
                    "renamed_characters": {"type": "boolean"},
                    "changed_setting": {"type": "boolean"},
                    "changed_ending": {"type": "boolean"},
                    "blended_sources": {"type": "boolean"},
                },
                "required": ["renamed_characters", "changed_setting", "changed_ending", "blended_sources"],
                "additionalProperties": False,
            },
        },
        "required": ["title", "new_setting", "beats", "transformation"],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT_TEMPLATE = (
    "You are a fiction writer for a transmigration/isekai + hidden-System serialized "
    "web-fiction YouTube channel (LitRPG style: status window, levels, skills, quests). "
    "You are given the narration transcript(s) of {n} other creator(s)' storytelling "
    "video(s) in this genre -- use them ONLY as loose inspiration for tone and trope, "
    "never as material to retell.\n\n"
    "Write a GENUINELY NEW story:\n"
    "- New named characters -- never reuse a name that appears in the source transcripts.\n"
    "- A new setting/world -- never the literal setting any source describes (a different "
    "world, era, or system rules).\n"
    "- A new scene order/pacing and a changed twist or ending.\n"
    "{blend_rule}"
    "- Write ONE chapter as a sequence of narration beats, ending on a cliffhanger into "
    "the next chapter.\n"
    "- Weave short System-notification lines (level up, skill acquired, quest update) "
    "into the narration like on-screen game UI.\n\n"
    "Write the narration in {language}. Give each beat a `type`: HOOK (first beat only), "
    "SETUP, BUILD, REVEAL, REACTION, ENDING (last beat only). Also give each beat a "
    "`visual_hint` (a short 3-10 word label of what's on screen) and a `visual_description` "
    "(a real, showable description of the scene for an illustrator -- character, action, "
    "location, mood).\n\n"
    "Also return `new_setting` (one short sentence naming the new world/setting you "
    "invented) and a `transformation` object honestly stating whether you renamed every "
    "character (`renamed_characters`), used a new setting (`changed_setting`), changed the "
    "ending (`changed_ending`), and -- only meaningful with 2+ sources -- merged ideas from "
    "more than one source rather than mainly retelling one (`blended_sources`).\n\n"
    "Return JSON only, no markdown, no explanation."
)
BLEND_RULE = "- Merge ideas from ALL of the sources into one story -- do not just retell one of them.\n"


def _build_system_prompt(source_count: int, target_language: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        n=source_count,
        blend_rule=BLEND_RULE if source_count > 1 else "",
        language=LANGUAGE_NAMES.get(target_language, target_language),
    )


def _build_user_message(payload: RewriteIn) -> str:
    lines = []
    for i, source in enumerate(payload.sources, 1):
        language = LANGUAGE_NAMES.get(source.language, source.language)
        lines.append(f"--- Source {i} ({source.label}, {language}) ---\n{source.text}")
    if payload.notes:
        lines.append(f"--- Context from the channel owner ---\n{payload.notes}")
    return "\n\n".join(lines)


def _check_transformation(out: RewriteOut, source_count: int) -> None:
    t = out.transformation
    missing = [
        axis
        for axis, ok in (
            ("renamed_characters", t.renamed_characters),
            ("changed_setting", t.changed_setting),
            ("changed_ending", t.changed_ending),
        )
        if not ok
    ]
    if source_count > 1 and not t.blended_sources:
        missing.append("blended_sources")
    if missing:
        raise ValueError(
            f"not transformed enough -- must change: {', '.join(missing)}. Rewrite so every one of those is true."
        )


def _shingles(text: str, n: int = OVERLAP_NGRAM) -> set[tuple[str, ...]]:
    words = re.findall(r"\S+", text.lower())
    if len(words) < n:
        return set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _overlap_ratio(generated: str, source: str) -> float:
    generated_shingles = _shingles(generated)
    if not generated_shingles:
        return 0.0
    return len(generated_shingles & _shingles(source)) / len(generated_shingles)


def _check_same_language_overlap(narration: str, sources: list[SourceIn], target_language: str) -> None:
    for i, source in enumerate(sources, 1):
        if source.language != target_language:
            continue  # translation alone already drives overlap near zero -- see module docstring
        ratio = _overlap_ratio(narration, source.text)
        if ratio > MAX_SAME_LANGUAGE_OVERLAP:
            raise ValueError(
                f"too close to source {i} ({source.label}): {ratio:.0%} same-language phrase overlap, "
                f"max {MAX_SAME_LANGUAGE_OVERLAP:.0%} -- transform the wording further, don't paraphrase closely."
            )


def _validate(parsed: dict, sources: list[SourceIn], target_language: str) -> RewriteOut:
    out = RewriteOut.model_validate(parsed)
    if len(out.beats) < MIN_BEATS:
        raise ValueError(f"only {len(out.beats)} beats, need at least {MIN_BEATS}")
    if out.beats[0].type != "HOOK":
        raise ValueError("the first beat must be type HOOK")
    if out.beats[-1].type != "ENDING":
        raise ValueError("the last beat must be type ENDING")
    for i, beat in enumerate(out.beats, 1):
        if not beat.narration.strip():
            raise ValueError(f"beat {i} has empty narration")
        if beat.type not in BEAT_TYPES:
            raise ValueError(f"beat {i} has unknown type {beat.type!r}")

    _check_transformation(out, len(sources))
    narration = " ".join(beat.narration for beat in out.beats)
    _check_same_language_overlap(narration, sources, target_language)

    out.title = out.title.strip()[:100] or "Untitled chapter"
    return out


def generate_story_remix(settings: Settings, payload: RewriteIn) -> RewriteOut:
    credentials = resolve_ai_credentials(settings)
    if credentials is None:
        raise ValidationError("No AI provider is configured. Go to Settings to choose a provider and enter an API key.")

    user_message = _build_user_message(payload)
    repair_note: str | None = None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        system = _build_system_prompt(len(payload.sources), payload.target_language)
        if repair_note:
            system += f"\n\nYour previous response was invalid: {repair_note}\nFix it and return valid JSON only."
        try:
            result = call_structured(
                credentials, system=system, user_message=user_message,
                output_schema=OUTPUT_SCHEMA, max_tokens=MAX_TOKENS, schema_name="story_remix",
            )
        except AIProviderError as exc:
            raise ExternalServiceError(f"AI provider call failed: {exc}") from exc
        if result.refused:
            raise ExternalServiceError("Request was refused by the model's safety filter.")
        if not result.text:
            raise ExternalServiceError("Model did not return any text content.")
        try:
            return _validate(json.loads(result.text), payload.sources, payload.target_language)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Story remix attempt %d/%d invalid: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
            repair_note = str(exc)

    raise ExternalServiceError(f"Could not write a sufficiently transformed story after {MAX_RETRIES + 1} attempts: {last_error}")


@router.post("/story-remix/rewrite", response_model=RewriteOut)
def rewrite_story(payload: RewriteIn, settings: Settings = Depends(get_settings)) -> RewriteOut:
    return generate_story_remix(settings, payload)
