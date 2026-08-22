# 97. Package AI Metadata: Opt-In AI-Written Title/Description/Thumbnail Text

**Commit:** `1440a69`

Real user report: the auto-generated title/description felt bland, and
asked whether the thumbnail text was pulled from the script and whether
AI generation would cost money. Investigation confirmed title/description
were purely deterministic -- `core_message`/`hook_text`/project name
truncated to a char limit, no AI involved -- and the thumbnail headline
was just that same title re-truncated, never a separate message.

## Design

Previewed real AI-generated examples against two of the user's own live
project scripts (via a throwaway script calling `app.modules.ai.llm_client`
directly, not wired into the app yet) before writing any product code --
first a plain informative tone, then tuned to a more sensational/clickbait
("giat gan") tone per feedback, then tightened for length per a second
round of feedback. The final system prompt (in `package_generate.py`)
bakes in both rounds directly.

New, **opt-in, off-by-default** `PackageProjectConfig.ai_metadata_enabled`
(a real, billed AI call, unlike every other artifact this stage
produces). Exposed as a checkbox in `NewVideoModal.tsx`, wired through
`CreateProjectRequest.ai_metadata_enabled` (same "set once at project
creation" shape as `outro_text`) into both the classic and "Generate Full
by AI" creation paths.

When enabled, `_generate_ai_metadata` calls the existing
`app.modules.ai.llm_client.call_structured` (the same provider-agnostic
Claude/OpenAI wrapper `content_generate.py`/`beat_generate.py` already
use) with the project's own script text, asking for a `title`,
`description`, and a **separate** `thumbnail_text` -- unlike the
deterministic path, the thumbnail no longer just echoes the title.
Precedence is manual override > AI (if enabled) > deterministic template,
consistently for both metadata.json's title/description and the
thumbnail's on-image headline.

## Cost control

Any billed AI call needed its own re-billing guard, matching this
codebase's existing "never re-bill an already-paid cost" precedent (e.g.
FactoryRun retry never re-renders). `_resolve_ai_metadata` caches the
result in `package.meta.json` keyed on a fingerprint of the script text +
engine version -- a re-run of `generate_project_package` (which happens
on every Package-stage retry/poll) reuses the cached AI text instead of
calling the provider again, and only a real script edit, a fresh opt-in,
or an explicit "Regenerate Package" (which already discards the whole
cache) triggers a new billed call. A failed call is never cached, so it
retries on the next real attempt rather than sticking with "no AI text"
forever. On any provider error/timeout/refusal/malformed JSON, the stage
silently falls back to the deterministic title/description/headline --
never hard-fails the Package stage over a billed API call going wrong.

Real measured cost against the user's own scripts: ~$0.004-0.008 per
video (gpt-5.6-luna, ~350-500 input tokens / ~140-360 output tokens).

## Key files

- `app/modules/beat/schemas.py` -- `PackageProjectConfig.ai_metadata_enabled`
- `app/modules/beat/router.py` -- `CreateProjectRequest.ai_metadata_enabled`, applied as a config override
- `app/api/v1/endpoints/package_generate.py` -- `AIMetadata`, `_generate_ai_metadata`, `_resolve_ai_metadata` (cache), `_resolve_title_text`/`_resolve_description_text` (precedence), `metadata_fingerprint` now hashes the AI result too
- `frontend/src/components/NewVideoModal.tsx` -- checkbox + cost hint
- `frontend/src/api/beat.ts` -- `CreateProjectRequest.ai_metadata_enabled`

## Verification

`tests/api/test_package_stage.py::AIMetadataTests` (5 new tests, AI
provider always mocked, same convention as `test_beat_generate.py`):
AI text wins when enabled, soft-fallback to deterministic on a simulated
provider timeout, manual override still wins over AI, an unchanged
script does not re-call the provider on `regenerate-metadata`, and the
provider is never called when the flag is off. Full `test_package_stage.py`
(21 tests) and `tests/modules/beat/` (84 tests) pass. `npx tsc -b --noEmit`
clean. Confirmed the `ai_metadata_enabled` flag flows through a real
`POST /projects` call end to end (checked the returned project's own
`config.package.ai_metadata_enabled`), then deleted that throwaway
project row.
