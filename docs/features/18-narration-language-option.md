# 18. Narration language option (Spanish -> English default, picker added)

AI Story and Video Composer were both hardcoded to Spanish. Added a
language choice to each and switched the defaults to English.

## AI Story (`backend/app/modules/ai/story/`)

- `models.py`: new `StoryJob.language` column (`STORY_LANGUAGES = ("english",
  "spanish", "vietnamese")`, default `"english"`).
- `service.py`: the system prompt was previously written *in* Spanish with
  a hardcoded "write in ESPANOL" instruction. Rewrote it in English,
  parameterized by `language` (`_build_system_prompt(style, language)`),
  so Claude is told which language to output in rather than the prompt
  itself being locked to one.
- `schemas.py`/`router.py`: `StoryGenerateIn.language` (validated against
  `STORY_LANGUAGES`, default `"english"`), passed through to `generate()`.
- Frontend: `StoryTab` in `AIContentPage.tsx` gained a language `<select>`
  next to the existing style picker; job cards show style + language.

## Video Composer (`backend/app/modules/video_composer/`)

- The `voice` field already existed end-to-end (form field -> service ->
  `VideoComposeJob.voice`), just defaulted to `es-ES-AlvaroNeural` with no
  frontend control to change it. Default changed to `en-US-GuyNeural`;
  added a `voice` `<select>` to `VideoComposerPage.tsx` with curated
  English/Spanish/Vietnamese male+female edge-tts voices, wired through
  `api/videoComposer.ts` -> the existing `voice` form field.
- Removed the hardcoded "(tiếng Tây Ban Nha)" wording from the page
  subtitle and script field label since the language is now a choice, not
  a fixed assumption.

## DB note

No migration system in this app (`Base.metadata.create_all` only, no
Alembic) -- per the precedent set in `ec48719` (Content Workflow), a new
NOT-NULL column on an existing table needs a manual `ALTER TABLE` against
the local dev DB. Ran that for `story_job.language`; `story_job` had 0 rows
locally so no backfill was needed.
