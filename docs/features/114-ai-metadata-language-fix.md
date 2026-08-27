# 114. AI Package Metadata Follows the Project's Content Language

**Commit:** `449ad64`

Real user report: English horror-shorts videos were getting **Vietnamese**
AI-written titles, descriptions and thumbnail text — and inconsistently
(one video English, the next Vietnamese, same batch).

## Cause

`_generate_ai_metadata`'s system prompt ([97](97-package-ai-metadata.md))
was hardcoded — *"a viral short-form video copywriter for a **Vietnamese**
storytelling channel"* — and only softly asked for output "in the SAME
language as the script". For a non-Vietnamese script the model was pulled
between the two and drifted. It never read the project's actual
`content.language`.

## Fix

- Prompt is now built per call with the project's own
  `config.content.language` (`en`/`es`/`vi`/`pt` → full name) and pins
  **every** output field to that language explicitly; the "Vietnamese
  channel" wording is gone.
- `AI_METADATA_ENGINE_VERSION` `v1 → v2`, and `language` folded into the
  AI-metadata sub-cache fingerprint, so an existing project regenerates
  (and re-bills once) instead of reusing wrong-language cached text.

## Key files

- `app/api/v1/endpoints/package_generate.py` — `_ai_metadata_system_prompt(language_name)`,
  `_generate_ai_metadata(script_text, language, settings)`,
  `_ai_metadata_fingerprint(script_text, language)`, `_resolve_ai_metadata`
  reads `draft.config.content.language`
- `tests/api/test_package_stage.py` — 2 new tests (prompt pins language;
  the call uses the project's content language)

## Verification

Full `test_package_stage.py` green (23 tests). Regenerated the two real
test videos via `POST /projects/{id}/regenerate-package`: both came back
English — "Why Was I in a 1974 Photo" / "He Saw Me Following Myself" —
with English thumbnail headlines.
