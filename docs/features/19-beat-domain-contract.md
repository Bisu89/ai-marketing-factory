# 19 — Beat Domain Contract

**Commit:** _(fill in after commit)_

## What it does

Defines the Beat domain for the future Video Factory
(see [video_factory_architecture.md](video_factory_architecture.md)): a
`Beat` is a declarative description of one segment of a video (order,
duration, type, narration, visual/motion/caption/audio requirements) — not
a video, and not responsible for rendering one. `BeatPlan` is an ordered,
validated collection of Beats derived from one script.

This is a contract-only slice: no API router, no database table, no
consumer yet. It exists so a later Asset/Motion/Video Composer integration
has a stable shape to build against.

## Key files

`backend/app/modules/beat/schemas.py` (the domain contract — `BeatType`,
`VisualRequirement`, `MotionConfig`, `CaptionConfig`, `AudioConfig`, `Beat`,
`BeatPlan`), `backend/app/modules/beat/service.py` (`save_beats_json`/
`load_beats_json`), `backend/tests/modules/beat/test_schemas.py`.

## Non-obvious design decisions

- **Pydantic models are the domain model, not a schema layer wrapping a
  separate dataclass/ORM model.** Every other module pairs `models.py`
  (SQLAlchemy) with `schemas.py` (Pydantic I/O shape). Beat has no database
  row to wrap, and Pydantic already provides validation + serialization +
  deserialization without any FastAPI/SQLAlchemy dependency, so adding a
  second, framework-independent dataclass layer that mirrors it field-for-
  field would be pure duplication with nothing to keep in sync against.
- **No database table.** `beats.json` (via `service.save_beats_json`/
  `load_beats_json`) is the only persistence — a `BeatPlan` is produced once
  from a script and handed off to whatever renders it, not state that's
  queried/mutated over time the way a `*_job` table is elsewhere in this
  app. Revisit if a future step needs to list/search past plans.
- **Ordering validation requires a contiguous 1-based sequence** (`1..N`,
  no gaps or duplicates), checked against each `Beat.order` value — not
  list position, so beats can be constructed/deserialized in any order.
- **Cross-module references stay bare `int`s with no FK**:
  `BeatPlan.video_id` and `VisualRequirement.asset_id` follow the existing
  `AIGenerationHistory.job_id`/`PublishLog.ai_story_job_id` precedent
  (see [video_factory_architecture.md](video_factory_architecture.md)) —
  provenance only, no relationship, no import of `app.modules.ai` or a
  future `app.modules.asset`.
- **Tests use stdlib `unittest`, not `pytest`.** `pytest` isn't a project
  dependency yet (`backend/requirements.txt` has none, and the venv doesn't
  have it installed); adding it wasn't in scope for this slice, so the
  tests use only the standard library to avoid an unrelated dependency
  change.

## Verification

`python -m unittest discover -s tests` — 16 tests covering valid
construction, invalid duration (zero/negative), invalid order (below 1,
blank id), invalid plan ordering (gap/duplicate/not-starting-at-1),
multi-beat ordering independent of list position, `total_duration`,
JSON serialization shape, JSON round-trip equality, and a real
save→load round trip through a temp `beats.json` file. All pass; no
existing tests existed before this to regress (`backend/tests/` had only
an empty `__init__.py`).
