"""Shared, provider-agnostic structured-output LLM call for every
app/modules/ai/* generator (story, hook, caption) plus content_generate.py/
beat_generate.py. Wraps both Anthropic Claude and OpenAI behind one
call_structured() so callers never branch on provider themselves -- mirrors
app.modules.voice.providers' own TTSProvider/get_provider() shape for
"pick 1 of N interchangeable backends" (local vs edge_tts), applied here
for the first time to the AI-content path. Unlike Voice, the provider
choice is a global Settings field (see resolve_ai_credentials below), not
per-project, since anthropic_api_key already was one.

Every output_schema passed into call_structured follows this codebase's
own existing convention: {"type": "json_schema", "schema": {...}}. Every
caller's actual schema already satisfies OpenAI's Structured Outputs
strict-mode rules as a side effect of how it was written for Anthropic
(every property required, additionalProperties: false at every object
level) -- so only the provider-specific wrapper differs, never the schema
itself.
"""

import time
from dataclasses import dataclass

import anthropic
import openai

from app.core.config import Settings

ANTHROPIC_MODEL = "claude-sonnet-5"
# Change here only -- nowhere else references a model name directly. User
# request 2026-08-19: switched from gpt-5-mini to gpt-5.6-luna.
OPENAI_MODEL = "gpt-5.6-luna"

AI_PROVIDERS = ("anthropic", "openai")


class AIProviderError(Exception):
    """Any non-timeout failure calling the configured AI provider."""


class AIProviderTimeoutError(AIProviderError):
    """The configured AI provider timed out."""


@dataclass(frozen=True)
class AICredentials:
    provider: str  # "anthropic" | "openai"
    api_key: str


def resolve_ai_credentials(settings: Settings) -> AICredentials | None:
    """The one place that decides "which provider, which key" -- every
    composition-root call site reads settings.anthropic_api_key directly
    today; this replaces that with a single provider-aware lookup. Returns
    None when the currently-selected provider has no key configured (the
    caller's own "not configured" check, mirroring the exact same shape
    `if not api_key` already had).
    """
    provider = settings.ai_provider
    key = settings.openai_api_key if provider == "openai" else settings.anthropic_api_key
    if not key:
        return None
    return AICredentials(provider=provider, api_key=key)


@dataclass
class LLMCallResult:
    """Normalized across both providers -- callers never see a raw SDK
    response object. `text` is the already-extracted structured-output JSON
    string (still the caller's own job to json.loads it); `refused` is True
    when the model's safety filter blocked the request (Anthropic's
    stop_reason == "refusal" / OpenAI's message.refusal being set).
    """

    text: str
    refused: bool
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


def _call_anthropic(api_key: str, system: str, user_message: str, output_schema: dict, max_tokens: int) -> LLMCallResult:
    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            output_config={"format": output_schema},
        )
    except anthropic.APITimeoutError as exc:
        raise AIProviderTimeoutError(str(exc)) from exc
    except anthropic.APIError as exc:
        raise AIProviderError(str(exc)) from exc

    text_block = next((b for b in response.content if b.type == "text"), None)
    usage = response.usage
    return LLMCallResult(
        text=text_block.text if text_block is not None else "",
        refused=response.stop_reason == "refusal",
        provider="anthropic",
        model=ANTHROPIC_MODEL,
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        latency_ms=0,  # filled in by call_structured
    )


def _call_openai(
    api_key: str, system: str, user_message: str, output_schema: dict, max_tokens: int, schema_name: str
) -> LLMCallResult:
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": output_schema["schema"]},
            },
        )
    except openai.APITimeoutError as exc:
        raise AIProviderTimeoutError(str(exc)) from exc
    except openai.APIError as exc:
        raise AIProviderError(str(exc)) from exc

    message = response.choices[0].message
    usage = response.usage
    return LLMCallResult(
        text=message.content or "",
        refused=bool(message.refusal),
        provider="openai",
        model=OPENAI_MODEL,
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        latency_ms=0,  # filled in by call_structured
    )


def call_structured(
    credentials: AICredentials,
    *,
    system: str,
    user_message: str,
    output_schema: dict,
    max_tokens: int,
    schema_name: str = "structured_output",
) -> LLMCallResult:
    start = time.monotonic()
    if credentials.provider == "openai":
        result = _call_openai(credentials.api_key, system, user_message, output_schema, max_tokens, schema_name)
    else:
        result = _call_anthropic(credentials.api_key, system, user_message, output_schema, max_tokens)
    result.latency_ms = int((time.monotonic() - start) * 1000)
    return result
