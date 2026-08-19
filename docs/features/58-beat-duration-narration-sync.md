# 58 — Auto-Sync Beat Duration to Narration Length + Folder Browse Fixes

**Commit:** `2cbe27a`

Two small real fixes found in manual testing.

## Beat duration auto-sync

Previously, attaching a local narration audio asset to a beat (Audio
step) never touched the beat's own `duration` — if the real audio
outlasted it, the user only found out at render time via a hard
validation error (`composition_render.py`'s `_resolve_narration`: "Beat N
narration is Xs but Beat duration is Ys"), with no obvious way to know
which number to fix.

`NarrationEditor`'s `handleNarrationSelected` (`VideoFactoryPage.tsx`) now
bumps `beat.duration` up to the real, already-known `asset.duration_sec`
(+0.2s buffer) whenever the narration is longer than the current
duration — mirroring Task 22's own Voice Factory pattern
(`voice_generate.py` already sets `Beat.duration` from measured audio
length for the auto Factory pipeline; this was just never wired into the
manual wizard's own narration picker). Never shrinks a duration the user
left intentionally longer than the narration (e.g. a lingering shot).

## Folder browsing fixed

`GET /settings/browse-folders` (used by both the Settings page's library
picker and the new Asset Library "Import Folder" browse button) called
`os.listdrives()` — a Python 3.12+-only API — on this app's own pinned
Python 3.11, raising `AttributeError` for every "list drives" request
(i.e. every time the dialog opened with no path yet). Replaced with a
plain per-letter `os.path.exists()` check, works on any Python version.
New `tests/api/test_settings.py` (4 tests) covers this — the module had
zero prior test coverage.

Also gave the Asset Library's "Import Folder" tab a "Browse..." button
(reusing the existing `FolderBrowserModal` component from the Settings
page) so folder paths don't have to be typed by hand.
