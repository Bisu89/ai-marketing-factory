# 144. Storyteller: image backgrounds/avatars + voice/speed picker

Follow-up to feature 143, both real user reports: no way to use a still
image as the background/avatar (only video loops), and no UI for voice/
narration speed despite the backend already supporting them.

**Key files**
- `backend/app/modules/storyteller/models.py` — `StorytellerAsset.media_type`
  (`image` | `video`)
- `backend/app/modules/storyteller/service.py` — `is_image_file`,
  `_probe_image_info`; `_sample_corner_color` reads a still image directly
  (no ffmpeg frame extraction needed); `_composite` uses ffmpeg's
  `-loop 1 -framerate 30 -t <duration>` still-image-as-video-stream
  technique for an image background/avatar instead of `-stream_loop -1`
- `backend/alembic/versions/0004_storyteller_media_type.py` — additive
  column, ALTER-only (no `create_all()` race like 0003 hit, since
  `create_all()` never adds columns to a table it didn't create)
- `frontend/src/pages/StorytellerPage.tsx` — voice picker (reuses Video
  Factory's own `VOICE_OPTIONS`, not a duplicate list), narration-speed
  picker, asset upload now accepts `image/*` too

**Verified:** 4 new tests (`is_image_file` extension matrix, real-ffmpeg
still-image background composite, real-ffmpeg still-image avatar colour-key
overlay) + the exact 0003-style create_all/upgrade race re-simulated on a
throwaway DB for 0004 specifically (confirmed a plain `ADD COLUMN` migration
doesn't have it, unlike `CREATE TABLE`) + a real dev-DB restart (data
confirmed intact: 89 projects, 492 assets, 3 videos).
