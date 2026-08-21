# 88. Background Music Picker in the Template Editor

**Commit:** `82b8466`

Real user follow-up after the narration/BGM debugging session
(docs/features/86): "does Settings have a place to pick music for a
template?" It didn't -- `EditTemplateModal` (added in
docs/features/84) only exposed Name/Description/Image style prompt;
`config.audio.music_enabled`/`bgm_mode`/`bgm_asset_id` had no UI at all
outside of a live project's own Step 4, and picking the wrong track
(the AUTO-selection-picks-a-stray-narration-file bug from 86) had no
way to be fixed at the template level without hand-editing the API.

## What it does

Added a "Background music" checkbox + "Choose Music" button to
`EditTemplateModal`, reusing the exact same `AssetBrowserModal
assetType="audio"` picker and "nothing chosen -> AUTO, a specific
track -> MANUAL bgm_mode" semantics `VideoFactoryPage`'s own picker
already established -- same picker, same backend fields, just a second
place to set them (template-level, not just per-project).

## A bug caught before it shipped

`EditTemplateModal` is itself a backdrop-with-onClick-to-close modal.
Nesting `<AssetBrowserModal>` (which has the identical
backdrop-onClick-to-close pattern, no `stopPropagation`) directly
inside it would have meant: clicking outside the picker to dismiss it
bubbles the click event up through the picker's own unstopped backdrop
handler into the *edit modal's* backdrop handler too, silently
discarding the in-progress edit. Fixed by rendering the two modals as
siblings inside a `Fragment` instead of nesting one inside the other's
DOM tree.

"Save as Template" (`VideoFactoryPage.tsx`) needed no equivalent
change -- unlike the image style prompt, music settings are already a
live, editable field on every project's own Step 4 Audio section, so
`buildProjectConfigForSave()` already captures whatever a project's
current BGM choice is.

## Verification

Real Playwright run against the actual running app: created a
throwaway template via the real API, opened its Edit modal (confirmed
default "Automatic" state), opened the music picker, searched "piano",
selected `emotional_piano.mp3`, confirmed the preview player and the
"Automatic" label disappearing, saved, and confirmed via a fresh `GET
/templates` that the backend now has `bgm_mode: "MANUAL"`,
`bgm_asset_id: 12` -- then deleted the throwaway template. Zero
console errors. `npx tsc -b --noEmit` clean.
