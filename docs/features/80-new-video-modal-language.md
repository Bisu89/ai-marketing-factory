# 80. Content Language in the "New Video" Modal

**Commit:** `5fc3ab4`

Real user report: the Dashboard's one-click "New Video" modal
(`NewVideoModal.tsx`) had no language control at all -- every built-in
Template hardcodes `content.language="en"`/`voice.language="en"` in its
own stored config, so a project created here was always English
regardless of which Template was picked, with no way to request e.g.
Vietnamese before Produce/auto-produce started. Vietnamese already
worked correctly on the classic Video Factory page's own Step 1 dropdown
(`docs/features/67-video-factory-content-language.md`) -- this modal was
simply missing the equivalent control.

## Fix

- `backend/app/modules/beat/router.py`'s `CreateProjectRequest` gained an
  optional `content_language: str | None = None` field (`None` = use the
  Template's own value, unchanged default behavior). When set,
  `create_project_endpoint` overrides `config.content.language` and
  `config.voice.language` on top of the resolved Template config, and
  auto-switches `voice.provider` to `edge_tts` when the language isn't
  English -- same precedence and same auto-switch reasoning
  `VideoFactoryPage.tsx`'s own Step 1 dropdown already uses (Local/SAPI5
  only has a real voice per language if the OS shipped that voice pack;
  Edge TTS has one for every `CONTENT_LANGUAGES` entry).
- `frontend/src/components/NewVideoModal.tsx` gained the same "Content
  language" dropdown Step 1 already has (reusing `CONTENT_LANGUAGES`/
  `CONTENT_LANGUAGE_LABELS`, defaulting to `"en"`), wired into both
  `createProject()` calls (the regular Create/Produce button and
  "Generate Full by AI").

## Verification

Real `POST /projects` calls against an isolated backend+DB: template
`emotional_story` + `content_language="vi"` -> `config.content.language
== "vi"`, `config.content.tone` unchanged (`"warm and emotional"`,
still the template's own value), `config.voice.language == "vi"`,
`config.voice.provider` auto-switched to `"edge_tts"`. Omitting
`content_language` entirely -> unchanged pre-existing behavior
(`"en"`/`"local"`). An invalid language code correctly 400s with the
real allowed-values list. `tests/api/test_factory_pipeline.py` (21
tests) re-run green -- `create_project` (the underlying service
function) wasn't touched, only the endpoint-level config override before
calling it. `npx tsc -b --noEmit` clean.
