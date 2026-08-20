# 67. Video Factory: Content Language Picker

**Commit:** `pending`

Real user report: AI-generated content always came out in English with no
way to change it, and captions looked huge and centered.

## Caption issue: no code change, existing control was just unused

The "Emotional Story" built-in template defaults to the `"big_statement"`
caption preset (`backend/app/modules/beat/schemas.py:785`), which is
`font_scale: 1.8` + ASS `alignment: 5` (middle-center) --
`backend/app/modules/video_composer/service.py:99`. `VideoFactoryPage`'s
Step 4 already has a "Caption style" dropdown covering all 6 presets
(including `"top"`, added in
[60-top-caption-preset.md](60-top-caption-preset.md) for this exact
complaint); switching it away from "Big Statement" fixes this with no
code change. Left as-is: changing the built-in template's own default was
explicitly out of scope for this pass.

## Language issue: real gap, fixed

`ContentProjectConfig.language` and `VoiceProjectConfig.language` both
default to `"en"` in both built-in templates
(`backend/app/modules/beat/schemas.py:788,791,809,812`), and there was
**no UI anywhere** to change either -- `buildProjectConfigForSave()` just
passed `projectConfig.content`/`projectConfig.voice.language` through
unchanged (confirmed by grepping the entire frontend for "language").

Added a "Content language" dropdown to Step 1 (Script) of
`VideoFactoryPage.tsx`, backed by a new `contentLanguage` state that
feeds both `content.language` and `voice.language` in
`buildProjectConfigForSave()` (kept in lockstep, matching the backend
schema's own stated intent), restored correctly when loading a saved
project or applying a template. Picking a non-English language also
auto-switches the existing Step 4 "Provider" dropdown to Edge TTS, since
the default Local/SAPI5 engine only has a voice for a language if the OS
itself shipped that voice pack -- still fully overridable via that same
dropdown. If a user does switch back to Local with a non-English language
selected, an inline hint explains why narration might fail.

`types/videoFactory.ts` gained `ContentLanguage`/`CONTENT_LANGUAGES`/
`CONTENT_LANGUAGE_LABELS` (en/vi/es/pt, mirroring backend
`CONTENT_LANGUAGES`).

## Verification

- `npx tsc -b --noEmit` -- clean.
- Real Playwright/Chromium run against an isolated backend+frontend pair
  (temp DB/ports, existing dev servers on 8000/5173 untouched): picked
  Vietnamese on Step 1 → confirmed no premature hint → confirmed Step 4's
  Provider really did auto-switch to `edge_tts` → manually reverted to
  Local → navigated back to Step 1 → confirmed the hint now appears.
  Zero console errors.
