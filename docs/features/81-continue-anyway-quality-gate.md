# 81. "Continue Anyway" for Warning-Only NEEDS_REVIEW

**Commit:** `8a24d32`

Real user report: a project paused at NEEDS_REVIEW with a single
`PACING_OUTLIER` warning ("Beat 05 (2.0s) is significantly different
from the project average (5.7s)"), Quality Score 95/100. Clicking
"Continue Production" appeared to hang/do nothing. Root cause confirmed
via live backend logs: "Continue Production" (`continue_run`) always
re-runs the full pre-render Quality Gate check from scratch
(`_run_quality_and_proceed`); since the user hadn't changed the beat
plan, the exact same warning was re-detected every time, re-pausing the
run at NEEDS_REVIEW again -- an unescapable loop, not a hang, and one
that also wastefully re-rendered every beat's motion clip + the audio
master on each attempt before re-hitting the same wall.

`evaluate_readiness`'s own docstring (`app/modules/quality/analyzer.py`)
already documented the intended behavior -- "NEEDS_REVIEW is
override-able ('Render Anyway'), BLOCKED is not" -- but no such override
was ever actually implemented for the Factory pipeline's `continue_run`.

## Fix

- `app/api/v1/endpoints/factory_pipeline.py`: `continue_run`/
  `_continue_run_sync`/`_run_quality_and_proceed` gain a `force: bool`
  parameter. `force=True` skips re-pausing on a NEEDS_REVIEW result (or
  a nonzero factory-level asset-confidence policy review count) and
  proceeds straight to render on the current BeatPlan. A real `BLOCKED`
  result is **never** bypassed by `force` -- that's still a hard
  content/asset problem, not a style/pacing preference, and continues to
  raise `FactoryStageError` exactly as before. `POST
  /factory-runs/{run_id}/continue?force=true` is the new surface (default
  `force=false` -- every existing caller is unaffected).
- `frontend/src/components/ProductionProgress.tsx`: a second "Continue
  Anyway" button next to "Continue Production" on the NEEDS_REVIEW card
  (not shown for the separate post-render Final QA review card -- that
  one stays "re-check the finished package," a different action this
  task doesn't extend).

## Verification

New test `tests/api/test_factory_pipeline.py::ReviewResumeTests::
test_force_continue_proceeds_without_fixing_the_beat_plan`: reproduces
the exact real scenario (a low-confidence asset match triggers
NEEDS_REVIEW), calls `continue_run(..., force=True)` **without** fixing
anything, and confirms the run reaches `QUEUED` with a real
`render_job_id` instead of pausing again -- also confirms
`requires_human_review` (the lifetime "this run once needed a human"
flag) stays `True`, since forcing through means "I saw it and I'm
proceeding anyway," not erasing that it happened. Full
`tests/api/test_factory_pipeline.py` suite (22 tests) re-run green.
`npx tsc -b --noEmit` clean.
