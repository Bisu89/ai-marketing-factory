"""LLM-backed script provider for the Vox Documentary Factory (feature 164).

Composition root, like beat_generate.py: the only place that joins
app.modules.documentary (script provider interface) with app.modules.ai
(call_structured). Importing this module registers the "llm" provider.

The model is only allowed to *arrange and phrase* the research claims it is
given. It never receives permission to add facts, and the output is checked
in code (claim ids must exist; the documentary service's factual review still
gates approval), so a hallucinated claim cannot silently reach gate 2.
"""

import json
import logging

from pydantic import ValidationError as PydanticValidationError

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import AIProviderError, call_structured, resolve_ai_credentials
from app.modules.documentary.schemas import SECTION_ORDER, OutlineItem, ScriptSection
from app.modules.documentary.script_providers import ScriptContext, ScriptProvider, register_provider
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Vietnamese narration for 8-10 minutes at ~3.3 syllables/s (script.SYLLABLES_PER_SECOND).
TARGET_WORDS = (1650, 1950)
MAX_TOKENS = 9000

_KINDS = list(SECTION_ORDER)

_OUTLINE_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["outline"],
        "properties": {
            "outline": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "summary", "claim_ids"],
                    "properties": {
                        "kind": {"type": "string", "enum": _KINDS},
                        "summary": {"type": "string"},
                        "claim_ids": {"type": "array", "items": {"type": "integer"}},
                    },
                },
            }
        },
    },
}

_SCRIPT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["sections"],
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "heading", "paragraphs"],
                    "properties": {
                        "kind": {"type": "string", "enum": _KINDS},
                        "heading": {"type": "string"},
                        "paragraphs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["text", "factual", "claim_ids"],
                                "properties": {
                                    "text": {"type": "string"},
                                    "factual": {"type": "boolean"},
                                    "claim_ids": {"type": "array", "items": {"type": "integer"}},
                                },
                            },
                        },
                    },
                },
            }
        },
    },
}

_RULES = (
    "You help write a Vietnamese historical documentary narration. "
    "You are given a list of RESEARCH CLAIMS, each with an id and a status "
    "(verified / disputed / unverified). Hard rules:\n"
    "1. Use ONLY the given claims as historical content. Do not add any fact, date, number, name, place or quotation "
    "that is not in a claim. If something is missing, leave it out rather than invent it.\n"
    "2. Every paragraph that states something about the past has factual=true and lists the claim ids it relies on. "
    "Only pure framing or transition sentences may have factual=false and no claim ids.\n"
    "3. Present 'disputed' claims explicitly as contested and mention the uncertainty note. Never state a 'disputed' "
    "claim as settled. Do not state 'unverified' claims as fact; prefer to omit them.\n"
    "4. Natural spoken Vietnamese, varied sentence rhythm, no repetitive filler, no sensational language that the claims do not support.\n"
    "5. The seven sections in order: " + ", ".join(_KINDS) + "."
)


def _claims_block(ctx: ScriptContext) -> str:
    lines = []
    for c in ctx.claims:
        note = f" | uncertainty: {c.uncertainty_note}" if c.uncertainty_note else ""
        src = f" | sources: {'; '.join(c.source_titles)}" if c.source_titles else ""
        lines.append(f"[{c.id}] ({c.status}) {c.text}{note}{src}")
    return "\n".join(lines)


def _credentials():
    creds = resolve_ai_credentials(get_settings())
    if creds is None:
        raise ValidationError("Chưa cấu hình AI API key (Anthropic hoặc OpenAI) trong Cài đặt — hãy dùng provider 'mock' hoặc thêm key.")
    return creds


def _call(system: str, user: str, schema: dict, name: str) -> dict:
    try:
        result = call_structured(
            _credentials(), system=system, user_message=user, output_schema=schema, max_tokens=MAX_TOKENS, schema_name=name
        )
    except AIProviderError as exc:
        raise ExternalServiceError(f"Gọi AI thất bại: {exc}") from exc
    if result.refused:
        raise ExternalServiceError("AI từ chối yêu cầu này.")
    logger.info(
        "documentary %s: provider=%s model=%s in=%s out=%s", name, result.provider, result.model,
        result.input_tokens, result.output_tokens,
    )
    try:
        return json.loads(result.text)
    except json.JSONDecodeError as exc:
        raise ExternalServiceError("AI trả về dữ liệu không phải JSON hợp lệ.") from exc


def _validated(items: list[dict], model: type[BaseModel]) -> list:
    try:
        parsed = [model.model_validate(i) for i in items]
    except PydanticValidationError as exc:
        raise ExternalServiceError(f"AI trả về cấu trúc không hợp lệ: {exc.errors()[0]['msg']}") from exc
    return parsed


class LLMScriptProvider(ScriptProvider):
    name = "llm"

    def make_outline(self, ctx: ScriptContext) -> list[OutlineItem]:
        user = (
            f"Topic: {ctx.topic}\nTitle: {ctx.title}\n\nRESEARCH CLAIMS:\n{_claims_block(ctx)}\n\n"
            "Write the outline: one item per section, in order, with a one-sentence summary in Vietnamese "
            "and the claim ids that section will use."
        )
        data = _call(_RULES, user, _OUTLINE_SCHEMA, "documentary_outline")
        return _validated(data.get("outline", []), OutlineItem)

    def make_script(self, ctx: ScriptContext, outline: list[OutlineItem]) -> list[ScriptSection]:
        outline_txt = "\n".join(f"- {o.kind}: {o.summary} (claims {o.claim_ids})" for o in outline)
        user = (
            f"Topic: {ctx.topic}\nTitle: {ctx.title}\n\nRESEARCH CLAIMS:\n{_claims_block(ctx)}\n\n"
            f"APPROVED OUTLINE:\n{outline_txt}\n\n"
            f"Write the full narration, about {TARGET_WORDS[0]}-{TARGET_WORDS[1]} Vietnamese words in total "
            "(only if the claims support that much; shorter is fine, padding with invented facts is not)."
        )
        data = _call(_RULES, user, _SCRIPT_SCHEMA, "documentary_script")
        return _validated(data.get("sections", []), ScriptSection)


register_provider(LLMScriptProvider())
