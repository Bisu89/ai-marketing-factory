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

import difflib
import json
import logging
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError as PydanticValidationError, field_validator

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import AICredentials, AIProviderError, call_structured, resolve_ai_credentials
from app.modules.beat.schemas import Beat, BeatPlan, BeatType

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_TOKENS = 8192
MIN_BEATS = 3
MAX_BEATS = 18
MAX_RETRIES = 1  # one bounded repair attempt -- not an elaborate retry framework

SUPPORTED_TYPES = [t.value for t in BeatType]

# Story-to-Scene Analysis (see docs/features/103-story-to-scene-analysis.md):
# the user pastes a complete story into the Script field with no manual beat
# splitting at all -- this prompt is the whole "AI does the rest" pipeline.
# Superseded the old, much shorter prompt (which only asked for a plain
# `visual_hint` and allowed "light trimming" of narration): this version
# splits by visual/emotional moment rather than by sentence, requires
# word-for-word narration preservation (Beat is later validated against
# the original script, see _validate_narration_matches_script), and asks
# for the richer per-beat fields Beat now has (visual_description, camera,
# lighting, emotion, location, time_of_day, continuity_notes) so
# imagegen_generate.py's _image_prompt() has real cinematic detail to work
# with instead of only a 3-10 word hint.
SYSTEM_PROMPT = (
    "You are an expert short-form video director and cinematographer. You take a "
    "complete narration script and turn it into a sequence of cinematic scenes "
    "(beats), each of which can be represented by exactly one generated image.\n\n"
    "STEP 1 -- Read the ENTIRE script first and understand it globally: who the "
    "main character is (age, appearance, gender), the setting/time period, the "
    "emotional arc from beginning to end, the important objects/locations, and "
    "where the story's biggest visual turning points are.\n\n"
    "STEP 2 -- Split the script into scenes based on VISUAL MOMENTS, not "
    "sentences. Start a new scene only when the location changes, time changes "
    "significantly, the main action changes, the emotional state changes "
    "significantly, an important story beat or symbolic object occurs, or the "
    "camera/visual focus would need to change significantly. Do NOT create a new "
    "scene for every sentence -- several short sentences that form one coherent "
    "visual moment (e.g. a routine described in a few short clauses) belong in "
    "the SAME scene. Only split a single sentence across scenes if it describes "
    "visually incompatible moments that cannot share one image. Ask yourself for "
    "each scene: \"what single image would best represent this part of the "
    "narration?\" -- if the answer is the same image for several sentences, keep "
    "them together.\n\n"
    "SCENE COUNT: do not target a fixed number. Let the number of distinct "
    "visual moments in the story decide it. As rough guidance only (do not force "
    "these if the story clearly needs more or fewer): a ~15-30s story usually "
    "becomes 4-7 scenes, ~30-60s becomes 6-12, ~60-90s becomes 8-16. Quality of "
    "the split matters far more than hitting a count. Each beat gets its own "
    "separately generated (and separately billed) image, so do not fragment a "
    "single visual moment into several near-identical beats -- very short "
    "adjacent beats (under ~3s each) will be mechanically merged afterward "
    "anyway, so there is no benefit to over-splitting.\n\n"
    "NARRATION -- this is the most important rule: every scene's `narration` "
    "must be an exact, word-for-word excerpt of the original script, in the "
    "original order. Do NOT paraphrase, summarize, invent, or drop any words. "
    "Do NOT add narration that wasn't in the script. Concatenating every scene's "
    "`narration` field back together, in order, must reproduce the original "
    "script (minor whitespace/line-break differences are fine; wording must "
    "not change). This is required because the narration is used verbatim for "
    "text-to-speech.\n\n"
    f"- Pick exactly one `type` from: {', '.join(SUPPORTED_TYPES)}.\n"
    "- `visual_description`: describe what should actually appear in the "
    "generated image -- SHOW the moment through body language, facial "
    "expression, environment, objects, and composition. Do not just restate the "
    "narration or an abstract emotion (bad: \"a lonely man\"; good: \"a "
    "28-year-old man sits alone on the edge of an unmade bed in a dim, cluttered "
    "apartment, shoulders hunched, staring at the floor, phone face-down beside "
    "him\"). If a character/visual style has been given to you below, reuse the "
    "exact same age/ethnicity/hair/build/clothing details in every scene that "
    "character appears in -- do not let them silently change between scenes "
    "unless the story explicitly describes a change (e.g. a slow transformation "
    "over many days should change gradually, not jump straight from the first "
    "state to the last).\n"
    "- `visual_hint`: a short (3-10 word) plain label for the same moment, kept "
    "for backward compatibility with older parts of this app -- not an "
    "image-generation prompt.\n"
    "- `location` and `time_of_day`: brief, e.g. \"small bedroom\" / \"early "
    "morning\". Leave unset only if genuinely not established by the story.\n"
    "- `emotion`: the character's emotional state in this scene, brief.\n"
    "- `camera`: a specific cinematic framing (e.g. wide establishing shot, "
    "medium shot, close-up, extreme close-up, over-the-shoulder, low angle, "
    "rear tracking shot). Vary this across scenes to match the emotional beat -- "
    "isolation reads well as a wide shot with negative space, an emotional "
    "realization as a medium close-up, an important object as a close-up. Avoid "
    "using the same framing for every scene.\n"
    "- `lighting`: should track the emotional arc (e.g. dim/muted early, "
    "neutral through the middle, warmer at a turning point, brighter/cleaner "
    "toward a hopeful ending) -- keep it believable and grounded, not "
    "artificially dramatic in every scene.\n"
    "- `continuity_notes`: one short sentence on anything the next scene needs "
    "to stay consistent with (character's position, clothing, an object, the "
    "location) so the sequence of scenes feels physically continuous, like "
    "consecutive shots in one video rather than unrelated images.\n"
    "- Estimate a realistic `duration` in seconds for how long that scene's "
    "narration takes to read aloud at a natural pace.\n\n"
    "If the script ends with a short, punchy final line (a hook, a title card "
    "moment, a turning point like \"Day 1 of 100.\"), give it its own final "
    "scene when that reads as a meaningful visual beat rather than folding it "
    "silently into the previous scene.\n\n"
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
                        "visual_description": {"type": "string"},
                        "location": {"type": "string"},
                        "time_of_day": {"type": "string"},
                        "emotion": {"type": "string"},
                        "camera": {"type": "string"},
                        "lighting": {"type": "string"},
                        "continuity_notes": {"type": "string"},
                    },
                    "required": [
                        "type", "narration", "duration", "visual_hint", "visual_description",
                        "location", "time_of_day", "emotion", "camera", "lighting", "continuity_notes",
                    ],
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
    # All optional context the Story-to-Scene Analysis UI can supply
    # alongside the pasted script (see docs/features/103-story-to-scene-analysis.md)
    # -- every one of these was already collected elsewhere in this app
    # before this feature (idea on CreateProjectRequest, character/visual
    # style as Template.image_style_prompt, tone/style/target_duration as
    # ContentProjectConfig) and is threaded in here rather than duplicated
    # as new project-level storage.
    idea: str | None = None
    character_description: str | None = None
    tone: str | None = None
    style: str | None = None
    target_duration: float | None = None

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
    # duration, visual_hint, and the richer scene fields below.
    return [
        Beat(
            id=f"beat_{index + 1:02d}",
            order=index + 1,
            type=item["type"],
            narration=item.get("narration") or None,
            duration=item["duration"],
            visual_hint=item.get("visual_hint") or None,
            visual_description=item.get("visual_description") or None,
            location=item.get("location") or None,
            time_of_day=item.get("time_of_day") or None,
            emotion=item.get("emotion") or None,
            camera=item.get("camera") or None,
            lighting=item.get("lighting") or None,
            continuity_notes=item.get("continuity_notes") or None,
        )
        for index, item in enumerate(raw_beats)
    ]


# Story-to-Scene Analysis's core "TTS-safety" guarantee: every word of the
# original script must end up in exactly one beat's narration, in order
# (see docs/features/103-story-to-scene-analysis.md). Whitespace/line-break
# differences are ignored (the model reflows paragraphs into scenes), but
# no word may be added, dropped, or reordered -- a single normalized-word
# comparison against the concatenated beat narration catches all three.
def _normalize_words(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _narration_diff_note(script: str, beats: list[Beat]) -> str | None:
    expected = _normalize_words(script).split()
    actual = _normalize_words(" ".join(b.narration or "" for b in beats)).split()
    if expected == actual:
        return None
    matcher = difflib.SequenceMatcher(None, expected, actual)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        expected_snippet = " ".join(expected[i1:i2])[:100] or "(nothing)"
        actual_snippet = " ".join(actual[j1:j2])[:100] or "(nothing)"
        return (
            "beat narration must reproduce every word of the original script, in order, with no "
            f"paraphrasing, additions, or omissions -- near word {i1}, the script says "
            f"\"{expected_snippet}\" but the beats said \"{actual_snippet}\" instead"
        )
    return "beat narration does not match the original script's word count"


def _build_user_message(
    script: str, *, idea: str | None, character_description: str | None,
    tone: str | None, style: str | None, target_duration: float | None,
) -> str:
    context_lines: list[str] = []
    if idea:
        context_lines.append(f"Story idea/premise: {idea}")
    if character_description:
        context_lines.append(
            "Character/visual style already configured for this project -- keep every scene's "
            f"visual_description consistent with this, do not contradict it: {character_description}"
        )
    if tone or style:
        context_lines.append(f"Tone: {tone or 'unspecified'}. Narrative style: {style or 'unspecified'}.")
    if target_duration:
        context_lines.append(
            f"Target video duration: roughly {target_duration:.0f} seconds -- pacing guidance only, "
            "do not force the scene count to hit this number."
        )
    if not context_lines:
        return script
    return "\n".join(context_lines) + "\n\nFull narration script:\n" + script


def _call_and_validate(
    credentials: AICredentials, script: str, user_message: str, repair_note: str | None,
) -> BeatPlan:
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
            user_message=user_message,
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
        diff_note = _narration_diff_note(script, beats)
        if diff_note:
            raise ValueError(diff_note)
        return BeatPlan(script_text=script, beats=beats)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, PydanticValidationError) as exc:
        raise ValueError(f"generated JSON did not match the Beat contract: {exc}") from exc


def generate_beat_plan(
    credentials: AICredentials | None, script: str, *,
    idea: str | None = None, character_description: str | None = None,
    tone: str | None = None, style: str | None = None, target_duration: float | None = None,
) -> BeatPlan:
    if credentials is None:
        raise ValidationError(
            "No AI provider is configured. Go to Settings to choose a provider and enter an API key."
        )

    user_message = _build_user_message(
        script, idea=idea, character_description=character_description,
        tone=tone, style=style, target_duration=target_duration,
    )

    repair_note: str | None = None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return _call_and_validate(credentials, script, user_message, repair_note)
        except ValueError as exc:
            logger.warning("Beat generation attempt %d/%d failed validation: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
            repair_note = str(exc)

    raise ExternalServiceError(f"Could not generate a valid beat plan after {MAX_RETRIES + 1} attempts: {last_error}")


@router.post("/beats/generate", response_model=BeatPlan, status_code=201)
def create_beat_plan(payload: BeatGenerateIn, settings: Settings = Depends(get_settings)) -> BeatPlan:
    return generate_beat_plan(
        resolve_ai_credentials(settings), payload.script,
        idea=payload.idea, character_description=payload.character_description,
        tone=payload.tone, style=payload.style, target_duration=payload.target_duration,
    )
