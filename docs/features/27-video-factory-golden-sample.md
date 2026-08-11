# 27 — Video Factory Golden Sample

**Commit:** _(fill in after commit)_

## What it does

A canonical, hand-authored example project —
`examples/video_factory/{beats,assets,motion,composition}.json` plus 5 real
placeholder JPEGs — proving the Beat, Asset, Motion, and Composition
contracts (Tasks 02–08) compose into one coherent, valid plan *before* any
end-to-end rendering exists to prove it. No rendering, no new production
code, no new abstractions — this is example data plus tests that load and
cross-check it.

The story: five beats (hook → 3 body → cta) about two travelers, "Anna and
Tom," totaling exactly 30 seconds, one local image per beat, 5 distinct
motion presets, captions, a music reference, and narration references —
matching this task's literal requirements.

## Key files

`examples/video_factory/{beats,assets,motion,composition}.json`,
`examples/video_factory/assets/beat_0{1-5}_*.jpg` (5 real 1080×1920 JPEGs,
generated via PIL), `backend/tests/examples/test_video_factory_golden_sample.py`.

## Design decisions

- **`assets.json` validates against `AssetOut`** (the resolved/registered
  shape — `id`, `path`, `is_ready`, etc.), not `AssetRegisterIn`. The task's
  acceptance chain ("beats.json → asset resolution contract → …") implies
  these are already-resolved assets a beat's `visual.asset_id` can point
  at directly, not raw registration requests still awaiting a database
  row. There's no real `Asset` table involved — this is a static JSON file
  loaded and validated with `AssetOut.model_validate()` directly, mirroring
  how `app.modules.asset.schemas.asset_to_out()` would shape a real one.
- **Asset image files are real** (created once via PIL, checked into the
  repo) so `assets.json`'s `path` values are genuinely resolvable, not just
  plausible-looking strings — verified by a dedicated test
  (`test_referenced_local_asset_files_exist_on_disk`). The referenced
  `music_path` in `composition.json` is **not** backed by a real audio
  file — synthesizing one would mean invoking ffmpeg, which is exactly the
  rendering this task says not to do; the contract only requires the field
  be a non-empty string, which it is.
- **Motion values in `composition.json`'s `SceneMotion` are hand-copied
  from `motion.json`'s `MotionPlan` entries, not computed.** This is
  deliberate and is what the chain-integrity tests actually verify — Task
  05's `SceneMotion` is a structurally-duplicated (not imported) type from
  Task 04's `MotionPlan` (see `app/modules/composition/schemas.py`'s module
  docstring), so proving "the composition really was built from the motion
  plan" requires the two to agree value-for-value, checked field by field
  in `test_scene_motion_numeric_values_match_the_motion_json_entry`.
- **"Asset resolution" and "motion contract" in the acceptance criteria's
  chain diagram are proven by cross-file assertions in test code, not by a
  new production "resolver" abstraction** — e.g.
  `test_scene_asset_resolution_matches_beat_visual_asset_id` confirms each
  beat's `visual.asset_id` (Task 02's bare, unresolved reference) equals
  the `Scene.source_asset_id` that ultimately got used. This satisfies "do
  not add new abstractions": the "resolution" is a dict lookup in test
  code, not a class.
- **A negative-test class (`InvalidVariantsAreRejectedTests`)** mutates
  copies of the golden sample into deliberately-broken variants (duplicate
  scene order, a zeroed-out asset id, an out-of-range motion scale, a
  non-contiguous beat order) and asserts each is rejected — proof the
  golden sample's validity isn't a fluke of lax schemas.

## Verification

`python -m unittest discover -s tests` — 219 tests total (35 new, all
`unittest`, no ffmpeg/network dependency, run in ~0.02s): individual
per-file validity (beats/assets/motion/composition each parse and satisfy
their own literal requirements — 5 beats, 30s total, 5 distinct motion
presets, a music reference, a narration reference, a caption preset),
9 chain-integrity tests (every scene references a real beat and a real
asset; scene order/duration match the source beat; scene motion matches
its motion.json entry exactly, both by preset name and by every numeric
field; the narration script contains every beat's narration; captions and
SFX carry over from beat to scene), and 4 negative tests. All pass; the
184 pre-existing tests are unaffected.
