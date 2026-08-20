# 68. Video Factory: "Regenerate Narration" Button

**Commit:** `pending`

Real user report (follow-up to Task 67): "I changed the voice at Step 4
and re-rendered, but the output is still the same as before."

## Root cause

`VideoFactoryPage.tsx`'s Render Video/Quick Render/Render Again all go
through the classic composition path
(`app/api/v1/endpoints/composition_render.py`), which composes using
whatever narration audio file is **already assigned** to each beat
(`beat.narration_asset_id`). It never re-synthesizes. Only the Factory
pipeline's own `GENERATING_VOICE` stage
(`app/api/v1/endpoints/voice_generate.py::generate_project_narration`)
does that, keyed off a fingerprint that *does* correctly include
provider/voice_id/language/speed/pitch -- but `VideoFactoryPage.tsx` has
no factory-run trigger anywhere. The backend already had exactly the
right escape hatch for this,
`POST /projects/{id}/regenerate-voice` (`api/voice.ts::regenerateVoice`,
explicitly bypasses the stage's own idempotent-reuse check) -- it just had
zero call sites in the frontend.

## Fix

Added a "Regenerate Narration" button to the Voice Factory section (Step
4), next to Provider/Voice/Speed. On click: saves the current beat plan
first (so the just-changed Provider/Voice/Speed/Content-language actually
land in the project's stored config, which is what `regenerate-voice`
reads), calls `regenerateVoice(projectId)`, then reloads the page (the
same recovery pattern this page already uses for "Could not load this
project's beats"). Disabled with an inline explanation when there's no
saved project yet or no beats. Added a permanent hint line explaining that
Provider/Voice/Speed/Content language do nothing by themselves until this
button is clicked.

## Verification

- `npx tsc -b --noEmit` -- clean.
- Real Playwright run: created a real Project via `POST /projects` +
  `PUT /projects/{id}/beat-plan` (one beat with narration text) against an
  isolated backend, opened it in the browser, clicked Regenerate
  Narration. Backend log confirms a real local SAPI5 synthesis ran
  (`comtypes` TTS engine) and `POST /projects/1/regenerate-voice` returned
  200. Re-fetched the project afterward: the beat's `narration_asset_id`
  went from `null` to a real asset id, and `start`/`end`/`duration` were
  recomputed from the actual synthesized audio length (3.0s → 3.698833s),
  confirming the button genuinely re-synthesizes rather than no-op'ing.
  Zero console errors. Existing dev servers on 8000/5173 untouched.
