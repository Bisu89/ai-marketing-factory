# 22 — Composition Contract

**Commit:** _(fill in after commit)_

## What it does

Defines the Composition domain for the future Video Factory
(see [video_factory_architecture.md](video_factory_architecture.md)): a
`CompositionPlan` is an ordered list of `Scene`s, each carrying everything
a future renderer needs — duration, source asset, motion, caption,
audio/SFX, transition, and output format — without performing any
rendering itself. Like the Beat ([19](19-beat-domain-contract.md)) and
Motion ([21](21-motion-domain-presets.md)) contracts, this is a
contract-only slice: no API router, no database table, no ffmpeg, no AI/TTS
provider.

## Key files

`backend/app/modules/composition/schemas.py` (the contract — `Scene`,
`CompositionPlan`, `SceneMotion`, `SceneCaption`, `SceneAudio`,
`SceneTransition`, `OutputFormat`, plus locally-owned `ScaleRange`/
`PositionRange`/`RotationRange`/`Easing`), `backend/app/modules/composition/service.py`
(`build_composition_plan`, `save_composition_json`/`load_composition_json`),
`backend/tests/modules/composition/`.

## Non-obvious design decisions

- **`SceneMotion`'s numeric shape (scale/position/rotation/easing, with the
  same value bounds) is duplicated from `app.modules.motion.schemas.MotionPlan`,
  not imported.** This task's own architecture rule ("modules never import
  modules") applies here even though Composition's whole purpose is to
  combine information that conceptually comes from Beat/Asset/Motion/
  captions/audio — importing any of those modules would violate it. This
  follows the same "duplicate the pattern, don't import the module"
  precedent already established for the tkinter folder-picker (duplicated
  verbatim across `scene_cutter/router.py` and `video_composer/router.py`)
  and for ffprobe helpers. `preset_name` is kept as a free, unvalidated
  string specifically to avoid also duplicating (and having to keep in
  sync with) Motion's preset enum — only the numeric fields that actually
  matter to a renderer are validated here.
- **No separate `duration` field on `SceneMotion`.** `app.modules.motion.schemas.MotionPlan`
  has its own `duration` (it can stand alone, e.g. to preview a preset).
  Once embedded in a `Scene`, a second duration field could disagree with
  `Scene.duration` — motion always animates across the whole scene, so
  there is exactly one duration, owned by `Scene`.
- **"Missing asset" is a structural contract check, not a live database
  lookup.** `Scene.source_asset_id` is a required, bare (`int`, no FK)
  reference to an `app.modules.asset` `Asset.id` — validated only for
  "was one assigned at all" (present, `> 0`), never "does it still exist in
  the database," since checking that would require importing
  `app.modules.asset`. This is consistent with every other cross-module
  reference in this codebase (e.g. `PublishLog.ai_story_job_id`,
  `BeatPlan.video_id`): a bare, unconstrained pointer, not a real FK.
- **`narration_script`/`voice`/`language` live on `CompositionPlan`, not
  per-`Scene`.** This is a deliberate hand-off design: these three fields
  map directly onto `app.modules.video_composer`'s existing, *unmodified*
  `script`/`voice` `POST /video-compose-jobs` form fields (see
  [video_factory_architecture.md](video_factory_architecture.md)'s §6),
  so a future renderer can consume a `CompositionPlan` without Video
  Composer's contract needing to change at all. Per-scene audio is scoped
  to just `sfx` (a sound-effect cue) for the same reason.
- **Composing a real `CompositionPlan` from live Beat/Asset/Motion module
  output is explicitly out of scope for this module.** `build_composition_plan()`
  is a thin constructor over already-built `Scene` objects, not an
  orchestrator — assembling those `Scene` objects out of a live `BeatPlan`
  + resolved `Asset` rows + `MotionPlan`s necessarily touches multiple
  modules at once, which only an application/service-level orchestrator
  (or the frontend) is allowed to do, per this task's own architecture
  guidance and Task 01's "no `VideoFactoryService`" finding. This module
  only owns the *shape* of the result.
- **No EventBus involvement.** Composition assembly is a synchronous,
  on-demand step driven by a user action (same reasoning as Beat/Motion,
  and consistent with `video_factory_architecture.md`'s finding that this
  pipeline has no legitimate use for pub/sub — nothing here reacts to a
  background event like `video.downloaded`).

## Verification

`python -m unittest discover -s tests` — 109 tests total (32 new for this
module: per-field range validation on `SceneMotion`/`Scene`/`SceneTransition`/
`OutputFormat`, scene ordering (gap/duplicate/out-of-list-order all
rejected or handled correctly by `order` value), duration calculation via
`total_duration`, missing-asset rejection (field omitted, zero, negative —
both via direct construction and via JSON deserialization), invalid-motion
rejection propagating through a nested `Scene`, JSON serialization shape
and round-trip equality, `build_composition_plan()` construction, and a
`composition.json` save/load round trip through a real temp file —
including one test that writes `beats.json` (via `app.modules.beat`) and
`composition.json` side by side in one `project/` directory, matching the
acceptance criteria's example layout). All pass; the 77 pre-existing tests
(Beat + Asset + Motion) are unaffected.
