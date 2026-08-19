# 55 — Dual AI Provider: Claude + OpenAI, Selectable in Settings

**Commit:** _(fill in after commit)_

Every AI text-generation call (Content Brief, Script, Beat Plan, plus the
older AI Story/Hook/Caption features) was hardcoded to Anthropic Claude via
one shared helper. Adds a second provider (OpenAI) and a Settings toggle to
pick either one, switchable anytime — no code change required to swap.

## Key pieces

- `app/modules/ai/claude_client.py` → renamed/rewritten as
  `app/modules/ai/llm_client.py`: `call_structured(credentials, ...)` now
  dispatches to Anthropic or OpenAI based on `credentials.provider`, and
  normalizes both providers' differently-shaped responses into one
  `LLMCallResult` (`text`, `refused`, `provider`, `model`, `input_tokens`,
  `output_tokens`, `latency_ms`) — callers no longer unpack a raw SDK
  response object. Mirrors `app.modules.voice.providers`' own
  `TTSProvider`/`get_provider()` "one of N interchangeable backends" shape.
- `resolve_ai_credentials(settings)` (same file): the one place that reads
  `settings.ai_provider` + the matching key and returns `AICredentials`, or
  `None` when the selected provider has no key configured.
- `app/core/config.py`: new `ai_provider: str = "anthropic"` and
  `openai_api_key: str | None = None` Settings fields (fully backward
  compatible — an `.env` with neither set behaves exactly as before).
- `app/api/v1/endpoints/settings.py`: `GET /settings` gains `ai_provider`,
  `has_anthropic_key`, `has_openai_key`, `has_ai_key`; new
  `PUT /settings/openai-key` and `PUT /settings/ai-provider`.
- Every one of the 11 real `settings.anthropic_api_key` call sites (both
  AI Story/Hook/Caption's routers/services, `content_generate.py`,
  `beat_generate.py`, `factory_pipeline.py`, `batch_render.py`) now goes
  through `resolve_ai_credentials(settings)` instead.
- Frontend: `SettingsPage.tsx` gained a Provider dropdown + a second
  (OpenAI) key field, both keys always editable regardless of which is
  active; `AIContentPage.tsx`'s "no key configured" check now reads the
  provider-agnostic `has_ai_key`.

## Non-obvious decisions

- Every existing `output_schema` already followed the same
  `{"type": "json_schema", "schema": {...}}` convention and already
  satisfied OpenAI's Structured Outputs strict-mode rules (every property
  required, `additionalProperties: false`) as a side effect of how it was
  written for Anthropic — no schema needed to change, only the
  provider-specific wrapper.
- `OPENAI_MODEL = "gpt-5-mini"` is a rough tier-match for
  `claude-sonnet-5` (both mid-tier, not the cheapest/nano option) — a
  single constant, easy to change later.
- The OpenAI SDK's real shape (`openai==3.3.0` — `chat.completions.create`,
  `response_format={"type":"json_schema","json_schema":{...}}`,
  `message.refusal`, `usage.prompt_tokens`/`completion_tokens`,
  `openai.APITimeoutError`/`openai.APIError`) was verified by downloading
  and reading the actual installed package source, not assumed.

## Tests

54 new/updated: `tests/api/test_beat_generate.py` (12, rewritten for the
new `LLMCallResult` shape), `tests/modules/ai/test_llm_client.py` (5, new
package, pure `resolve_ai_credentials` logic). No automated test calls a
real AI provider (matches the pre-existing precedent — `call_structured`
itself was never tested against a real API, always mocked at that
boundary); live verification was manual, using the user's own OpenAI key
through the running dev server.

## Cost

No change to $0 local pipeline stages. AI text generation itself was
already the only paid cost in this app (a few cents/video); this task adds
a cheaper alternative provider, not a new cost.
