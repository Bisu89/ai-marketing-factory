"""AI-generated Beat plans -- the adapter boundary between the existing
AI infrastructure (app.modules.ai.llm_client -- Claude or OpenAI, see
docs/features/55-dual-ai-provider.md) and the Beat domain contract
(app.modules.beat.schemas). See docs/features/30-generate-beats.md.

Per app/modules/README.md, no module may import another module.
app.modules.beat must not import app.modules.ai (or vice versa); something
has to call Claude and hand the result to BeatPlan for validation, and per
this codebase's established "composition root" convention (see
composition_render.py's own module docstring for the precedent), that
translation lives here: app/api/v1/endpoints/* is core HTTP-layer
infrastructure, not a module under app/modules/, so it may import both.

No database persistence, unlike story/hook/caption (which each persist a
Job+Version per Library video): a Beat plan generated here isn't tied to a
video_id -- it's a stateless script-in, BeatPlan-out call, and the Video
Factory frontend keeps the result in local component state for now.
"""

import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError as PydanticValidationError, field_validator

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import AICredentials, AIProviderError, call_structured, resolve_ai_credentials
from app.modules.beat.schemas import Beat, BeatPlan, BeatType

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_TOKENS = 4096
MIN_BEATS = 4
MAX_BEATS = 8
MAX_RETRIES = 1  # one bounded repair attempt -- not an elaborate retry framework

SUPPORTED_TYPES = [t.value for t in BeatType]

SYSTEM_PROMPT = (
    "You are an expert short-form video editor who breaks narration scripts "
    "into a sequence of visual story beats.\n\n"
    f"Given a narration script, split it into roughly {MIN_BEATS}-{MAX_BEATS} beats. "
    "For each beat:\n"
    "- Preserve the original narrative meaning -- do not invent new plot points.\n"
    "- Reuse the script's own wording for `narration` wherever possible (light "
    "trimming for pacing is fine; do not paraphrase into new sentences).\n"
    f"- Pick exactly one `type` from: {', '.join(SUPPORTED_TYPES)}.\n"
    "- Write a short (roughly 3-10 word) `visual_hint` describing what should be "
    "on screen -- a plain description, not an image-generation prompt, asset ID, "
    "or file name.\n"
    "- Estimate a realistic `duration` in seconds for how long that beat's "
    "narration takes to read aloud at a natural pace.\n\n"
    "Each beat gets its own separately generated image, so keep beat lengths "
    "reasonably even -- aim for roughly 4-7 seconds of narration per beat. Do not "
    "give one short sentence (or two short adjacent sentences) their own separate "
    "beat -- combine short adjacent narration into a single beat instead of "
    "producing several beats under ~3 seconds each.\n\n"
    "Do not generate asset IDs, image URLs, motion presets, captions, or audio "
    "configuration -- those are decided by a later step, not you.\n\n"
    "Return structured JSON only, matching the provided schema."
)

OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "beats": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": SUPPORTED_TYPES},
                        "narration": {"type": "string"},
                        "duration": {"type": "number"},
                        "visual_hint": {"type": "string"},
                    },
                    "required": ["type", "narration", "duration", "visual_hint"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["beats"],
        "additionalProperties": False,
    },
}


class BeatGenerateIn(BaseModel):
    script: str

    @field_validator("script")
    @classmethod
    def _script_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("script must not be blank")
        return value


# Real user report: the AI sometimes still produces adjacent short beats
# (e.g. 3.1s + 2.0s) despite the prompt's own guidance above -- prompt
# compliance alone doesn't guarantee it, and each beat gets its own
# separately-billed AI-generated image (Task 59, $0.006 each, see
# app.modules.ai.image_client.IMAGE_COST_USD) regardless of how short its
# narration is, so an unmerged short beat is pure wasted cost with no
# visual benefit. This deterministically merges a short beat into its
# preceding neighbor -- guaranteed, not dependent on the model listening --
# whenever that doesn't produce an unnaturally long combined beat or
# collapse the plan too aggressively.
_MIN_BEAT_DURATION_FOR_MERGE_SEC = 3.0
_MAX_MERGED_BEAT_DURATION_SEC = 9.0
_MIN_TOTAL_BEATS_AFTER_MERGE = 3


def _merge_short_beats(raw_beats: list[dict]) -> list[dict]:
    """Operates on the AI's raw (pre-Beat-object) output, before
    _beats_from_raw assigns id/order -- so id/order stay purely mechanical
    afterward, exactly as before. Only ever merges backward (a short beat
    into the one immediately before it) -- a short opening beat (a Hook,
    often deliberately punchy) is left alone since there's no natural
    predecessor to fold it into.
    """
    if len(raw_beats) <= _MIN_TOTAL_BEATS_AFTER_MERGE:
        return raw_beats

    merged: list[dict] = [dict(raw_beats[0])]
    for item in raw_beats[1:]:
        duration = float(item.get("duration") or 0)
        prev = merged[-1]
        prev_duration = float(prev.get("duration") or 0)
        if duration < _MIN_BEAT_DURATION_FOR_MERGE_SEC and prev_duration + duration <= _MAX_MERGED_BEAT_DURATION_SEC:
            prev_narration = (prev.get("narration") or "").strip()
            item_narration = (item.get("narration") or "").strip()
            prev["narration"] = f"{prev_narration} {item_narration}".strip()
            if not prev.get("visual_hint"):
                prev["visual_hint"] = item.get("visual_hint")
            prev["duration"] = round(prev_duration + duration, 2)
        else:
            merged.append(dict(item))

    if len(merged) < _MIN_TOTAL_BEATS_AFTER_MERGE:
        return raw_beats  # merging collapsed the plan too aggressively -- keep the AI's original split instead
    return merged


def _beats_from_raw(raw_beats: list[dict]) -> list[Beat]:
    # id/order are mechanical, not creative -- assigned here deterministically
    # rather than trusted from the model, so a malformed/duplicate/gapped id
    # or order can never come back from the LLM in the first place. The
    # model only ever has to get the *content* right: type, narration,
    # duration, visual_hint.
    return [
        Beat(
            id=f"beat_{index + 1:02d}",
            order=index + 1,
            type=item["type"],
            narration=item.get("narration") or None,
            duration=item["duration"],
            visual_hint=item.get("visual_hint") or None,
        )
        for index, item in enumerate(raw_beats)
    ]


def _call_and_validate(credentials: AICredentials, script: str, repair_note: str | None) -> BeatPlan:
    system_prompt = SYSTEM_PROMPT
    if repair_note:
        system_prompt += (
            f"\n\nYour previous response was invalid: {repair_note}\n"
            "Fix it and return valid JSON only, respecting all of the constraints above."
        )

    try:
        result = call_structured(
            credentials,
            system=system_prompt,
            user_message=script,
            output_schema=OUTPUT_SCHEMA,
            max_tokens=MAX_TOKENS,
            schema_name="beat_plan",
        )
    except AIProviderError as exc:
        raise ExternalServiceError(f"AI provider call failed: {exc}") from exc

    if result.refused:
        raise ExternalServiceError("Request was refused by the model's safety filter.")

    if not result.text:
        raise ExternalServiceError("Model did not return any text content.")

    # Everything below is "did the model's JSON match the Beat contract?",
    # not a transport/API failure -- these are the errors worth a bounded
    # repair retry (see generate_beat_plan), unlike the AIProviderError /
    # refusal / empty-content cases above, which fail immediately.
    try:
        parsed = json.loads(result.text)
        raw_beats = parsed["beats"]
        if not raw_beats:
            raise ValueError("model returned zero beats")
        raw_beats = _merge_short_beats(raw_beats)
        beats = _beats_from_raw(raw_beats)
        return BeatPlan(script_text=script, beats=beats)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, PydanticValidationError) as exc:
        raise ValueError(f"generated JSON did not match the Beat contract: {exc}") from exc


def generate_beat_plan(credentials: AICredentials | None, script: str) -> BeatPlan:
    if credentials is None:
        raise ValidationError(
            "No AI provider is configured. Go to Settings to choose a provider and enter an API key."
        )

    repair_note: str | None = None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return _call_and_validate(credentials, script, repair_note)
        except ValueError as exc:
            logger.warning("Beat generation attempt %d/%d failed validation: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
            repair_note = str(exc)

    raise ExternalServiceError(f"Could not generate a valid beat plan after {MAX_RETRIES + 1} attempts: {last_error}")


@router.post("/beats/generate", response_model=BeatPlan, status_code=201)
def create_beat_plan(payload: BeatGenerateIn, settings: Settings = Depends(get_settings)) -> BeatPlan:
    return generate_beat_plan(resolve_ai_credentials(settings), payload.script)
