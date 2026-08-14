# 29 — Beat Domain Contract v2

**Commit:** _(fill in after commit)_

## What it does

Rewrites `app.modules.beat`'s `Beat`/`BeatPlan` contract ([19](19-beat-domain-contract.md))
to match a stricter, narrower spec: `Beat` is now just
`id, order, type, narration, duration, visual_hint` -- the nested
`visual`/`motion`/`caption`/`audio` sub-objects are gone. A Beat no longer
carries a resolved `asset_id` or a motion/caption/sfx choice; it only
describes *what* a segment needs (a plain-text `visual_hint`), leaving
asset/motion/caption assignment to later pipeline steps that build
`composition.json` directly.

`BeatType` changed from `hook/body/cta/outro` to the new
`HOOK/SETUP/BUILD/REVEAL/REACTION/ENDING/BODY` (serialized uppercase).
`BeatPlan.total_duration` is now a `@computed_field` (present in
`model_dump_json()` output, not a settable field) instead of a plain
`@property`, and `BeatPlan` now rejects an empty beat list and duplicate
beat ids (previously only order-contiguity was checked).

## Key files

`backend/app/modules/beat/schemas.py` (rewritten),
`backend/tests/modules/beat/test_schemas.py` (rewritten),
`examples/video_factory/beats.json` (updated to the new shape),
`backend/tests/examples/test_video_factory_golden_sample.py` (removed
assertions on now-gone `beat.visual/.motion/.caption/.audio`).

## Why the golden sample's chain-integrity tests shrank

Tasks 07/08 originally had `beats.json` carry `motion.preset`,
`caption.text/preset`, and `audio.sfx` so the golden sample could prove
those values flowed from `beats.json` into `composition.json`. Since Beat
no longer carries that data, `test_scene_asset_resolution_matches_beat_visual_asset_id`,
`test_scene_caption_matches_beat_caption`, and `test_scene_sfx_matches_beat_audio_sfx`
were removed (nothing on `Beat` for them to compare against anymore) --
the remaining chain checks (id/order/duration/narration agreement between
`beats.json` and `composition.json`) still hold.

## Regression

`python -m unittest discover -s tests` -- 228 tests, all passing.

## Next task

Task 2 -- Generate Beats.
