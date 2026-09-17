# Storyteller: slideshow layout (many images, Ken Burns zoom)

User feedback on the triptych layout: a static split-screen still doesn't
hold attention for a 10-15 minute video. Adds a third layout: upload many
images, the script is split into one "beat" per image, and each image gets
its own on-screen time (matching how much narration plays over it) plus a
random zoom in/out (Ken Burns) so nothing on screen is ever fully static.

## What it does

- `layout: "slideshow"` + ordered `slide_asset_ids`. `split_into_beats(text, n)`
  divides the script into exactly `n` near-equal word groups (one per
  image); each beat is narrated on its own (still chunked through the
  existing `chunk_script` for TTS-length safety), so its real narrated
  duration becomes that image's on-screen time.
- Each image panel gets a random zoom direction (in or out) and a random
  max zoom (1.12x-1.28x) via ffmpeg's `zoompan`, sized so the zoom
  completes over exactly that panel's own duration -- a 3s beat and a 30s
  beat both traverse their full zoom range once, not at different speeds.
  Video slides (mixed in freely) just play, no zoom.
- Panels are `hstack`-free here -- `concat`enated in sequence instead of
  stacked side by side, since a slideshow is one image at a time, not a
  split screen. Captions/disclaimer/story-info overlays work the same as
  the other two layouts.
- Frontend: an ordered picker (add from an image pool, reorder with up/down,
  remove) instead of a fixed set of dropdowns, since the image count is
  arbitrary. Submit is blocked under 2 images.

## Verified

- `split_into_beats`: exact group count, no word lost, near-equal sizes,
  clamps `n` down for very short scripts (unit tests).
- Real ffmpeg: generated images, mixed image+video slides, empty-slides
  fallback, slideshow + captions + disclaimer + story-info together (all
  in `test_composite.py`).
- Real HTTP round-trip (TestClient): 3-image slideshow episode ->
  `completed`, playable 372KB mp4, in ~22s.
- Migration `0006_storyteller_slideshow.py` (1 additive nullable JSON
  column): downgrade/upgrade round-tripped on a copy of the real dev DB
  with the existing episode row intact throughout; real dev DB row counts
  unchanged after the column landed for real (project 89, asset 492,
  video 3, series 6, storyteller_episode 1).

Files: `backend/app/modules/storyteller/{models,schemas,router,service}.py`,
`backend/alembic/versions/0006_storyteller_slideshow.py`,
`backend/tests/modules/storyteller/{test_chunking_and_captions,test_composite,test_service_crud}.py`,
`frontend/src/{types,api}/storyteller.ts`, `frontend/src/pages/StorytellerPage.{tsx,css}`.
