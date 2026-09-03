"""Content Engine (Task 21 -- see docs/features/47-content-brief-script-engine.md):
the composition-root adapter between the existing AI infrastructure
(app.modules.ai.llm_client -- Claude or OpenAI, see
docs/features/55-dual-ai-provider.md) and the Project/BeatPlan domain
contract (app.modules.beat.schemas) for the new Idea -> ContentBrief ->
Script stages, ahead of Beat generation. Same "app/api/v1/endpoints/* may
import both modules; the modules may never import each other"
composition-root shape app/api/v1/endpoints/beat_generate.py already
established for Script -> Beat -- this is that identical pattern one stage
earlier.

    AI Client (app.modules.ai.llm_client.call_structured)
          |
    Content Service (generate_content_brief / generate_script, below)
          |
    Prompt Builder (_build_*_prompt, below -- language-aware, no giant
          |         prompt strings live in factory_pipeline.py or the API layer)
    Structured Output Parser (json.loads against a real JSON schema, then
                               validated Pydantic models -- never arbitrary
                               markdown parsing, section 11)

No image/video/I2V generation anywhere in this file (section 4) -- AI is
used only for Idea->Brief and Brief->Script; the flattened Script becomes a
plain `script_text` string, which is exactly what the existing, unmodified
beat_generate.py already expects. Beat/Visual/Quality/Render are untouched.
"""

import hashlib
import json
import logging
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError as PydanticValidationError, field_validator

from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import AICredentials, AIProviderError, AIProviderTimeoutError, call_structured, resolve_ai_credentials
from app.modules.beat.project_service import get_project_draft, set_project_generated_content
from app.modules.beat.schemas import ContentBrief, ContentProjectConfig

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TOKENS = 2048
# Two bounded repair attempts (3 calls total). There are two independent
# transient failure modes now -- a malformed-JSON response, and a provider
# returning an empty 200 (observed intermittently from gpt-5.6-luna, the
# same "unofficial/flaky endpoint" shape edge_tts has) -- and a single-shot
# failure of the very first Factory stage is a poor experience.
MAX_RETRIES = 2

# Section 12/13 -- shared between _build_script_system_prompt (states the
# target as an explicit word count, not just seconds) and
# validate_script_text (checks the same number) so the two can never drift
# apart. Real OpenAI behavior observed in manual testing: leaving the
# target as "approximately N seconds when read aloud" alone, with no
# explicit word count, let gpt-5-mini write 2-3x the intended length even
# though Claude generally stayed within tolerance from the same prompt --
# stating the actual number removes the ambiguity for either provider.
SCRIPT_LENGTH_TOLERANCE = 0.35

# Task 21 section 28 -- stable, machine-readable codes; never a raw provider
# error string surfaced to the UI (section 28's own explicit instruction).
CONTENT_GENERATION_FAILED = "CONTENT_GENERATION_FAILED"
CONTENT_PROVIDER_TIMEOUT = "CONTENT_PROVIDER_TIMEOUT"
INVALID_CONTENT_RESPONSE = "INVALID_CONTENT_RESPONSE"
SCRIPT_TOO_SHORT = "SCRIPT_TOO_SHORT"
SCRIPT_TOO_LONG = "SCRIPT_TOO_LONG"
SCRIPT_VALIDATION_FAILED = "SCRIPT_VALIDATION_FAILED"

# Display name per ContentProjectConfig.language code (section 36/37 -- an
# explicit, configured language, never inferred). Distinct from
# app.modules.ai.story.service.LANGUAGE_NAMES (keyed by full English words,
# not these short codes) -- not reused since the key shape differs and this
# module must not import app.modules.ai.story.
LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "vi": "Vietnamese", "pt": "Portuguese"}


class ContentProviderTimeout(ExternalServiceError):
    """The Anthropic call itself timed out -- section 28/29: retryable,
    distinct from a generic failure (see app.modules.factory.schemas'
    ERROR_CLASSIFICATION, which maps this to TRANSIENT).
    """


class InvalidContentResponse(ExternalServiceError):
    """The model returned content that couldn't be parsed into the expected
    shape at all (bad JSON, wrong keys) -- distinct from ScriptValidationError
    below, which is a real, well-formed Script that just fails this
    project's own length/structure rules.
    """


class _TransientProviderError(Exception):
    """A retryable provider hiccup within one generate_* attempt loop -- an
    empty 200 response or a refused flag on a request that has no business
    being refused. Never surfaced to a caller (the loop either succeeds on
    a retry or converts it to InvalidContentResponse); kept distinct from
    ValueError so a genuine JSON/schema failure still carries its own
    repair_note back into the next attempt's prompt.
    """


class ScriptValidationError(ValidationError):
    """Carries one of SCRIPT_TOO_SHORT/SCRIPT_TOO_LONG/SCRIPT_VALIDATION_FAILED
    so the caller (factory_pipeline.py) doesn't have to re-derive which one
    from the message text.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# -- Script: the structured AI output, flattened to plain script_text ------
#
# Never persisted as its own object (section 10's "if the existing Script
# model already exists, reuse it" -- Project.script_text, already
# established since Task 13, already *is* that model from every other call
# site's point of view). Structured only long enough to validate section
# 11's "AI must not return arbitrary prose the rest of the factory can't
# understand" and to be able to check hook/body/ending exist independently.


class Script(BaseModel):
    hook: str
    body: list[str]
    ending: str
    cta: str | None = None

    @field_validator("hook", "ending")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("body")
    @classmethod
    def _body_not_empty(cls, value: list[str]) -> list[str]:
        if not value or not any(line.strip() for line in value):
            raise ValueError("body must contain at least one non-blank line")
        return value

    def to_narration_text(self) -> str:
        """The flat string beat_generate.py's own, unmodified
        generate_beat_plan() expects -- hook + body lines + ending (+ cta,
        when present) joined as natural narration paragraphs.
        """
        parts = [self.hook, *self.body, self.ending]
        if self.cta and self.cta.strip():
            parts.append(self.cta)
        return "\n\n".join(p.strip() for p in parts if p and p.strip())


# -- ContentBrief generation: Idea -> ContentBrief --------------------------

BRIEF_OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "audience": {"type": "string"},
            "angle": {"type": "string"},
            "emotion": {"type": "string"},
            "hook_strategy": {"type": "string"},
            "tone": {"type": "string"},
            "pacing": {"type": "string"},
            "core_message": {"type": "string"},
            "cta": {"type": "string"},
        },
        "required": ["topic", "audience", "angle", "emotion", "hook_strategy", "tone", "pacing", "core_message", "cta"],
        "additionalProperties": False,
    },
}


def _build_brief_system_prompt(content: ContentProjectConfig) -> str:
    language_name = LANGUAGE_NAMES.get(content.language, content.language)
    return (
        "You are a content strategist for short-form social video. Given a one-line video idea, "
        "produce a structured creative brief that a scriptwriter will use next -- do not write the "
        "script itself.\n\n"
        f"Target audience default: {content.audience}. Target tone: {content.tone}. Style: {content.style}.\n"
        f"All text fields must be written in {language_name}.\n\n"
        "Fields:\n"
        "- topic: a one-sentence restatement of what this video is actually about.\n"
        "- audience: who this specific video is for (refine the default above using the idea itself).\n"
        "- angle: the specific take/explanation this video will use.\n"
        "- emotion: the single dominant feeling this video should create in the viewer.\n"
        "- hook_strategy: the technique the opening line should use (e.g. unexpected observation, "
        "direct question, bold claim).\n"
        "- tone: the writing tone for the script (refine the default above).\n"
        "- pacing: how the script should move (e.g. fast, slow build, steady).\n"
        "- core_message: the one idea a viewer should walk away with.\n"
        "- cta: what the viewer should do or think at the end.\n\n"
        "Return structured JSON only, matching the provided schema."
    )


def _call_brief(credentials: AICredentials, idea: str, content: ContentProjectConfig, repair_note: str | None) -> ContentBrief:
    system_prompt = _build_brief_system_prompt(content)
    if repair_note:
        system_prompt += f"\n\nYour previous response was invalid: {repair_note}\nFix it and return valid JSON only."

    try:
        with ai_generation_semaphore:
            result = call_structured(
                credentials, system=system_prompt, user_message=idea,
                output_schema=BRIEF_OUTPUT_SCHEMA, max_tokens=MAX_TOKENS, schema_name="content_brief",
            )
    except AIProviderTimeoutError as exc:
        raise ContentProviderTimeout(f"AI provider call timed out: {exc}") from exc
    except AIProviderError as exc:
        raise ExternalServiceError(f"AI provider call failed: {exc}") from exc

    if result.refused:
        raise _TransientProviderError("The model returned a refusal for a routine request.")
    if not result.text:
        raise _TransientProviderError("The model returned an empty response.")

    try:
        parsed = json.loads(result.text)
        return ContentBrief.model_validate(parsed)
    except (json.JSONDecodeError, TypeError, PydanticValidationError) as exc:
        raise ValueError(f"generated JSON did not match the ContentBrief contract: {exc}") from exc


def generate_content_brief(credentials: AICredentials | None, idea: str, content: ContentProjectConfig) -> ContentBrief:
    if credentials is None:
        raise ValidationError(
            "No AI provider is configured. Go to Settings to choose a provider and enter an API key."
        )
    repair_note: str | None = None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return _call_brief(credentials, idea, content, repair_note)
        except ValueError as exc:
            logger.warning("Content brief attempt %d/%d failed validation: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
            repair_note = str(exc)
        except _TransientProviderError as exc:
            # An empty 200 / spurious refusal -- retry without a repair_note
            # (the previous response wasn't "wrong", it was absent). A real
            # ContentProviderTimeout is deliberately NOT caught here: it is
            # already a distinct, classified TRANSIENT error and propagates
            # as before.
            logger.warning("Content brief attempt %d/%d hit an empty provider response: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
    raise InvalidContentResponse(f"Could not generate a valid content brief after {MAX_RETRIES + 1} attempts: {last_error}")


# -- Script generation: ContentBrief -> Script ------------------------------

SCRIPT_OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "hook": {"type": "string"},
            "body": {"type": "array", "items": {"type": "string"}},
            "ending": {"type": "string"},
            "cta": {"type": "string"},
        },
        "required": ["hook", "body", "ending", "cta"],
        "additionalProperties": False,
    },
}


def _build_script_system_prompt(brief: ContentBrief, content: ContentProjectConfig, words_per_second: float) -> str:
    language_name = LANGUAGE_NAMES.get(content.language, content.language)
    cta_instruction = (
        f'End with a clear call to action: "{brief.cta}".' if content.cta_enabled
        else "Do not include a call to action."
    )
    target_words = content.target_duration * words_per_second
    min_words = round(target_words * (1 - SCRIPT_LENGTH_TOLERANCE))
    max_words = round(target_words * (1 + SCRIPT_LENGTH_TOLERANCE))
    return (
        "You are an expert scriptwriter for short-form social video narration. Write a narration script "
        "entirely from the creative brief below -- do not invent new facts, names, or claims not implied "
        "by it.\n\n"
        f"Topic: {brief.topic}\n"
        f"Audience: {brief.audience}\n"
        f"Angle: {brief.angle}\n"
        f"Target emotion: {brief.emotion}\n"
        f"Hook strategy: {brief.hook_strategy}\n"
        f"Tone: {brief.tone}\n"
        f"Pacing: {brief.pacing}\n"
        f"Core message: {brief.core_message}\n\n"
        f"Target length: approximately {content.target_duration:.0f} seconds when read aloud at a natural pace, "
        f"which means the hook + body + ending + cta combined must total roughly {target_words:.0f} words -- "
        f"never fewer than {min_words} words and never more than {max_words} words. Count your words before "
        f"answering; a script outside this range will be rejected.\n"
        f"Write entirely in {language_name}, with no mixing of languages.\n"
        f"{cta_instruction}\n\n"
        "Structure the response as:\n"
        "- hook: one short, attention-grabbing opening line.\n"
        "- body: an ordered list of narration lines/paragraphs that develop the core message.\n"
        "- ending: a closing line that lands the emotion.\n"
        "- cta: the call-to-action line (empty string if none).\n\n"
        "Return structured JSON only, matching the provided schema. Be written to be read aloud, not as "
        "on-screen text."
    )


def _call_script(
    credentials: AICredentials, brief: ContentBrief, content: ContentProjectConfig, words_per_second: float,
    repair_note: str | None,
) -> Script:
    system_prompt = _build_script_system_prompt(brief, content, words_per_second)
    if repair_note:
        system_prompt += f"\n\nYour previous response was invalid: {repair_note}\nFix it and return valid JSON only."

    try:
        with ai_generation_semaphore:
            result = call_structured(
                credentials, system=system_prompt, user_message=brief.topic,
                output_schema=SCRIPT_OUTPUT_SCHEMA, max_tokens=MAX_TOKENS, schema_name="script",
            )
    except AIProviderTimeoutError as exc:
        raise ContentProviderTimeout(f"AI provider call timed out: {exc}") from exc
    except AIProviderError as exc:
        raise ExternalServiceError(f"AI provider call failed: {exc}") from exc

    if result.refused:
        raise _TransientProviderError("The model returned a refusal for a routine request.")
    if not result.text:
        raise _TransientProviderError("The model returned an empty response.")

    try:
        parsed = json.loads(result.text)
        return Script.model_validate(parsed)
    except (json.JSONDecodeError, TypeError, PydanticValidationError) as exc:
        raise ValueError(f"generated JSON did not match the Script contract: {exc}") from exc


def generate_script(
    credentials: AICredentials | None, brief: ContentBrief, content: ContentProjectConfig, words_per_second: float,
) -> Script:
    if credentials is None:
        raise ValidationError(
            "No AI provider is configured. Go to Settings to choose a provider and enter an API key."
        )
    repair_note: str | None = None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            script = _call_script(credentials, brief, content, words_per_second, repair_note)
            # Real length misses observed in manual testing (see
            # SCRIPT_LENGTH_TOLERANCE's own docstring) -- fed back into the
            # same bounded repair-retry loop as a malformed-JSON failure,
            # not left as a single-shot failure the user has to manually
            # retry from scratch.
            validate_script_text(script.to_narration_text(), content.target_duration, words_per_second)
            return script
        except ValueError as exc:
            logger.warning("Script attempt %d/%d failed validation: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
            repair_note = str(exc)
        except ScriptValidationError as exc:
            logger.warning("Script attempt %d/%d failed length validation: %s", attempt + 1, MAX_RETRIES + 1, exc)
            if attempt == MAX_RETRIES:
                raise  # preserve the real SCRIPT_TOO_LONG/SCRIPT_TOO_SHORT code for the caller
            last_error = exc
            repair_note = str(exc)
        except _TransientProviderError as exc:
            logger.warning("Script attempt %d/%d hit an empty provider response: %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc
    raise InvalidContentResponse(f"Could not generate a valid script after {MAX_RETRIES + 1} attempts: {last_error}")


# -- Script validation (section 12/13/14) -----------------------------------


def validate_script_text(
    script_text: str, target_duration: float, words_per_second: float, tolerance: float = SCRIPT_LENGTH_TOLERANCE
) -> None:
    """Section 12: hook/body/ending existence is already enforced by Script's
    own Pydantic validators before this is ever called (never a bare string
    with no structure -- see generate_script). This validates the *flattened*
    text's approximate length against the template's target duration
    (section 13's own words = duration x speech_rate formula), with a
    generous, configurable tolerance (section 12: "do not demand exact
    timing yet -- voice timing is handled later," Task 22).
    """
    if not script_text or not script_text.strip():
        raise ScriptValidationError(SCRIPT_VALIDATION_FAILED, "Script is empty.")

    word_count = len(script_text.split())
    target_words = target_duration * words_per_second
    min_words = target_words * (1 - tolerance)
    max_words = target_words * (1 + tolerance)

    if word_count < min_words:
        raise ScriptValidationError(
            SCRIPT_TOO_SHORT,
            f"Script is {word_count} words for a {target_duration:.0f}-second template "
            f"(expected roughly {target_words:.0f}, minimum {min_words:.0f}).",
        )
    if word_count > max_words:
        raise ScriptValidationError(
            SCRIPT_TOO_LONG,
            f"Script is {word_count} words for a {target_duration:.0f}-second template "
            f"(expected roughly {target_words:.0f}, maximum {max_words:.0f}).",
        )


# -- Content fingerprint + duplicate idea detection (section 30-33) --------


def content_fingerprint(idea: str, template_id: str | None, content: ContentProjectConfig) -> str:
    """Section 31: a deterministic hash of (normalized idea, template,
    language, content profile) -- NOT the Project's identity (section 31's
    own explicit warning), purely a "would this produce the same content
    request" signal for future reuse-detection. Normalizes the idea the
    same way normalize_idea() (app.modules.batch.schemas) does, so two
    differently-cased/punctuated but equal ideas fingerprint identically.
    """
    normalized_idea = re.sub(r"\s+", " ", idea.strip().lower()).strip(".,!?;: ")
    payload = "|".join([
        normalized_idea, template_id or "", content.language, content.tone, content.style,
        f"{content.target_duration:.1f}", content.audience, str(content.cta_enabled),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# -- API: explicit "Regenerate Script" (section 15) -------------------------


@router.post("/projects/{project_id}/regenerate-script", response_model=None, status_code=200)
def regenerate_script(project_id: int, settings: Settings = Depends(get_settings)) -> dict:
    """Section 15: explicit user action, bypasses the CONTENT stage's own
    idempotent "skip if a script already exists" reuse check on purpose --
    unlike an automatic FactoryRun pass, a direct Regenerate click always
    re-runs Idea -> ContentBrief -> Script (even over a locked script; an
    explicit request always wins, same "manual retry may exceed automatic
    limits" precedent Task 19 established). The freshly generated content
    is AI-authored again, so script_locked stays False (set_project_generated_content
    never sets it) and stale beats are cleared (section 50's Script ->
    Beat invalidation chain). Requires a real idea; a project with no idea
    has nothing to regenerate from.
    """
    draft = get_project_draft(project_id)
    idea = (draft.idea or "").strip()
    if not idea:
        raise ValidationError("This project has no idea to regenerate a script from.")

    content_config = draft.config.content
    credentials = resolve_ai_credentials(settings)
    brief = generate_content_brief(credentials, idea, content_config)
    script = generate_script(credentials, brief, content_config, settings.content_words_per_second)
    script_text = script.to_narration_text()
    validate_script_text(script_text, content_config.target_duration, settings.content_words_per_second)

    set_project_generated_content(project_id, brief, script_text)
    return {"project_id": project_id}
