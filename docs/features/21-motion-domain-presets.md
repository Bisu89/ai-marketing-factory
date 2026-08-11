# 21 — Motion Domain and Presets

**Commit:** _(fill in after commit)_

## What it does

Defines the Motion domain for the future Video Factory
(see [video_factory_architecture.md](video_factory_architecture.md)): a
`MotionPlan` is a deterministic, declarative Ken-Burns-style instruction
(scale/position/rotation over a duration, with an easing curve) for how a
still image or video scene should move on screen — it does not render
anything. Nine presets are defined and resolvable by name:
`static`, `slow_push_in`, `slow_pull_out`, `pan_left`, `pan_right`,
`pan_up`, `pan_down`, `zoom_and_pan`, `subtle_rotate`.

Like [19-beat-domain-contract.md](19-beat-domain-contract.md), this is a
contract-only slice: no API router, no database table, no ffmpeg. It
exists so a later rendering step (Task 01's `beat/motion/` render worker)
has a stable, already-validated instruction to consume instead of
reinventing preset parameters at render time.

## Key files

`backend/app/modules/motion/schemas.py` (the contract — `Easing`,
`MotionPresetName`, `ScaleRange`, `PositionRange`, `RotationRange`,
`MotionPlan`), `backend/app/modules/motion/service.py` (the preset
registry and `build_motion_plan()`), `backend/tests/modules/motion/`.

## Non-obvious design decisions

- **Field names are `start`/`end`, not the task brief's illustrative
  `from`/`to`.** `from` is a reserved Python keyword; matching it exactly
  would need Pydantic alias plumbing (`Field(alias="from")` plus
  `populate_by_name`/`by_alias` at every dump/load call) for a "Conceptually:"
  example, not a literal spec. `start`/`end` carries identical meaning
  without that overhead.
- **Same "Pydantic models are the domain model" call as the Beat module**
  (see [19-beat-domain-contract.md](19-beat-domain-contract.md)) — no
  parallel dataclass layer, for the same reason: nothing here needs
  FastAPI/SQLAlchemy independence beyond what Pydantic already provides,
  and a mirrored second layer would only duplicate every field.
- **Scale is bounded to `[1.0, 4.0]` on both ends, not just validated
  as positive.** A Ken-Burns effect pans/zooms *within* the source frame;
  going below `1.0` (zooming out past the source's native size) would
  reveal the frame's edges once actually rendered, so `1.0` is enforced as
  a hard floor even though this module never renders anything itself —
  every preset's own default data honors this too (see the
  `test_every_preset_keeps_scale_at_or_above_one` test).
- **Rotation is capped at ±30°**, which is what actually makes
  `subtle_rotate` subtle by construction rather than by convention — a
  future caller can't accidentally build a disorienting full-spin preset
  through this contract.
- **`build_motion_plan()`'s `duration` override is re-validated through
  `MotionPlan`'s own constructor, not patched into a copied object.**
  Pydantic's `model_copy(update=...)` deliberately skips validation, which
  would let an out-of-range override silently bypass the same bounds a
  direct `MotionPlan(...)` call enforces — `build_motion_plan` instead
  rebuilds via `model_dump()` + `MotionPlan(**data)` so every path re-runs
  the same checks.
- **No API router.** Nothing yet renders a `MotionPlan` or needs to reach
  it over HTTP; adding a router ahead of a real consumer would be
  speculative surface area, same reasoning as the Beat module.

## Verification

`python -m unittest discover -s tests` — 77 tests total (35 new for this
module: per-field range validation on `ScaleRange`/`PositionRange`/
`RotationRange`/`MotionPlan`, JSON serialization shape and round-trip,
all 9 presets registered and each building a valid, semantically-sane plan
(e.g. `static` has zero movement, pans move position without rotating,
`subtle_rotate` actually rotates, every preset's scale stays ≥ 1.0),
invalid-preset rejection (both as a raw string to `build_motion_plan` and
inside a `MotionPlan` directly), duration-override validation, and
deterministic-output equality across repeated calls). All pass; the 42
pre-existing tests (Beat + Asset) are unaffected.
