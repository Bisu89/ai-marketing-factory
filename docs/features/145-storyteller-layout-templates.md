# Storyteller: layout templates (triptych) + disclaimer/story-info overlays

Adds a second layout mode to the Storyteller module, matching a real competitor
"đọc truyện" channel format the user shared and analysed: three side-by-side
video/image panels instead of one background + avatar-corner overlay.

## What it does

- `StorytellerEpisode.layout`: `"single"` (existing background+avatar) or
  `"triptych"` (three panels — `left`/`middle`/`right_asset_id` — each scaled
  to 1/3 width, `hstack`ed). Panels can mix video and still images freely; no
  colour-keying needed since triptych panels are self-contained.
- Optional overlays on either layout: `disclaimer_text` (top drawtext) and a
  story-info card (`story_title`/`story_author`/`story_character`, bottom
  drawtext block).
- Frontend: layout `<select>` on the create-episode form; single shows the
  existing background/avatar pickers, triptych shows left/middle/right
  pickers (pooled from all assets); disclaimer + 3 story-info text inputs.

## Design decisions

- `_Panel` (`path`, `is_image`, `key_color`) decouples `_composite()` from DB
  rows so ffmpeg-graph tests don't need a database.
- Triptych panels skip colour-keying entirely (unlike single-mode avatar
  overlay) — they're full opaque video/image panels, not overlays.

## Bugs caught during verification

- `hstack` filtergraph had a stray leading comma (`...,hstack=inputs=3[bg]`)
  from a `"".join(...)` builder — ffmpeg failed with `No such filter: ''`.
- `_escape_drawtext()` (copied from `outro/renderer.py`) escaped apostrophes
  as `\\'`, which is invalid inside a single-quoted ffmpeg filter value —
  it terminates the quote early instead of escaping it. Fixed with the
  correct break-out-and-reopen form: `'\''`. Caught by a real-apostrophe test
  case, confirmed fixed with actual ffmpeg execution.

## Verified

- 30/30 storyteller tests pass; full repo test collection (1375 tests) clean.
- Real HTTP round-trip (TestClient, isolated DB): triptych + disclaimer +
  story-info episode → `completed`, real 52605-byte mp4.
- Migration `0005_storyteller_layouts.py` (8 additive columns) run against
  the real dev DB: existing episode preserved, `project`/`asset`/`video`/
  `series` row counts unchanged (89/492/3/6).

Files: `backend/app/modules/storyteller/{models,schemas,router,service}.py`,
`backend/alembic/versions/0005_storyteller_layouts.py`,
`backend/tests/modules/storyteller/test_composite.py`,
`frontend/src/{types,api}/storyteller.ts`,
`frontend/src/pages/StorytellerPage.{tsx,css}`.
