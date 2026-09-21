# Storyteller: optional background music, ducked under narration

Adds a `music` asset kind and a `music_asset_id` picker to any layout
(single/triptych/slideshow) -- surfaced by real usage: a test zombie
episode had no music at all, and horror-style ambience is standard for
this niche.

## What it does

- `StorytellerAsset.kind` gains `"music"` (`media_type="audio"`, probed via
  duration only -- no width/height/key_color).
- `_mix_narration_and_music()`: narration + looped music, ducked via
  ffmpeg's `sidechaincompress` (music level drops while narration speaks),
  same technique as `video_composer/audio_mix.py`'s `mix_audio`, duplicated
  and simplified (no SFX cues -- storyteller has no SFX concept) per this
  module's isolation convention. Runs once, before compositing; `_process()`
  hands `_composite()` the mixed file in place of raw narration --
  `_composite()` itself needed zero changes since it only ever treats that
  path as "the final audio track".
- Frontend: a "Nhạc nền" picker (applies to every layout) + a third asset
  library column for uploading/managing music clips.

## Verified

- Real ffmpeg: no-music passthrough, music shorter than narration (loops
  to cover), music longer than narration (trimmed to video duration), and
  the mixed output feeding into `_composite()` like plain narration.
- `save_asset(kind="music", ...)` probes `media_type="audio"` (duration
  only, no crash from trying to read a video stream off an audio file).
- Real end-to-end: a 15-minute zombie-apocalypse test episode re-rendered
  with a synthesized ominous drone track (ffmpeg-generated placeholder --
  detuned low sines + brown noise + tremolo, not a licensed track) ducked
  under Vietnamese narration; 56.1MB mp4, correct 900s duration.
- Migration `0007_storyteller_music.py` (1 additive nullable column)
  verified on a copy of the real dev DB, then run for real with all row
  counts unchanged (project 91, asset 555, video 3, series 6).
- 52/52 storyteller tests pass (1 pre-existing timestamp-collision flake
  in `test_list_episodes_newest_first`, passes in isolation); 1398 tests
  collect repo-wide.

Files: `backend/app/modules/storyteller/{models,schemas,router,service}.py`,
`backend/alembic/versions/0007_storyteller_music.py`,
`backend/tests/modules/storyteller/*.py`,
`frontend/src/{types,api}/storyteller.ts`, `frontend/src/pages/StorytellerPage.{tsx,css}`.
