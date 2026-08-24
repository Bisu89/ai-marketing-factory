# 102. Template Voice & Caption Controls

**Commit:** `f91d36c`

Real user report: the Create/Edit Template modals (added in
[101](101-create-template-button.md)) had no voice or caption size/position
controls at all — a template's captions/voice were silently carried over
unseen and unchangeable. Copying the built-in "Emotional Story" template
silently carried over its actual `captions.preset="big_statement"` (large,
vertically centered text), which is what the user was seeing as "text huge
in the middle" with no way to notice or fix it.

## What was added

To both `CreateTemplateModal.tsx` and `EditTemplateModal.tsx`:
- Captions enabled checkbox + caption preset `<select>` (`CAPTION_PRESETS`/
  `CAPTION_PRESET_LABELS` from `types/videoFactory.ts`), with a hint
  explaining "Big statement" is large/centered vs. the others sitting near
  an edge.
- Voice provider `<select>` (local / edge_tts), a conditional voice
  `<select>` (local voices fetched via `listLocalVoices()`, or the existing
  `VOICE_OPTIONS` list for edge_tts), and a voice speed range slider.

`VOICE_OPTIONS` was moved from a local `const` in `VideoFactoryPage.tsx` to
a shared export in `types/videoFactory.ts` so both modals could reuse it
without duplicating the list.

No backend changes — `POST /templates`/`PUT /templates/{id}` already
accepted `captions`/`voice` as part of `config`; the modals just weren't
sending or exposing them.

## Verification

`npx tsc -b --noEmit` clean. Real end-to-end verification via a headless-
Chromium driver script: opened Settings → New Template → picked "Copy of
'Emotional Story'" and confirmed the caption style dropdown now visibly
shows "Big statement" (the actual root cause, now surfaced); changed it to
"Emotional (highlight box)", switched voice provider to Edge TTS, picked
"Vietnamese (Female)", set speed to 1.3x, saved, then fetched the template
back via `GET /templates` and confirmed the persisted config matched
exactly (`preset: "emotional"`, `provider: "edge_tts"`,
`voice_id: "vi-VN-HoaiMyNeural"`, `speed: 1.3`). Deleted the test template
afterward via `DELETE /templates/{id}`.
