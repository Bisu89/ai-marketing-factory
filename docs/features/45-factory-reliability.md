# 45 — Factory Reliability: Persistent Checkpoints + Crash-Safe Resume

**Commit:** `7652e3a`

Hardens Task 18's `FactoryRun` orchestration to survive an app crash or
Windows restart mid-production without losing work or silently repeating
expensive stages. No new module, no second workflow engine — extends
`app.modules.factory` and its composition root (`factory_pipeline.py`) in
place.

## What was already solid from Task 18

`FactoryRun` was already the durable, SQLite-backed source of truth (no
in-memory dicts), startup reconciliation already existed, retry was already
stage-specific, and a completed `VideoComposeJob` already implies a real,
ffprobe-validated `final.mp4` (Task 10's atomic-output work) — so render
output could never be silently trusted invalid. This task's job was the
remaining gaps: no per-stage audit trail independent of the single
`status` field, no retry-attempt tracking, no error classification, and a
COMPLETED run silently reused forever even after the project was edited.

## New: `FactoryCheckpoint`

One row per `(factory_run_id, stage)` — `status`
(PENDING/RUNNING/COMPLETED/FAILED/SKIPPED), `attempt`, `started_at`/
`completed_at`, `error_code`/`error_message`, a small `checkpoint_metadata`
JSON blob (beat counts, assignment counts, quality outcome — never a full
BeatPlan/thumbnail/log). A real FK to `factory_run.id` (both tables live in
this module, unlike `FactoryRun`'s own bare cross-module ints). Retrying a
stage re-enters its existing row (`attempt` += 1) rather than appending a
new one. `factory_pipeline.py`'s every stage transition now calls
`start_checkpoint`/`complete_checkpoint`/`skip_checkpoint`/`fail_checkpoint`
alongside its existing `FactoryRun.status` update; `_mark_failed` (the
single funnel for every failure path) settles both together so they can
never disagree. New `GET /factory-runs/{id}/checkpoints`.

## New: `FactoryRun.attempt` + error classification

`attempt` (default 1, incremented by `retry_run`) plus a stable
`ERROR_CLASSIFICATION` table (`TRANSIENT`/`PERMANENT`/`USER_ACTION_REQUIRED`)
covering every code this module or a delegated `RenderJob` can set, exposed
on `FactoryRunOut` as computed `error_classification`/`max_attempts_reached`
(`FACTORY_MAX_ATTEMPTS = 3`). Both are informational only — this app has no
automatic retry loop (every retry is a user-triggered POST), so nothing is
ever blocked; the classification exists so the frontend can eventually
phrase Retry correctly ("try again" vs. "fix this first").

## Real gap found and fixed: stale COMPLETED reuse

Task 18's `create_and_start_run` returned an already-COMPLETED run
unchanged forever, even if the user edited the Beat/asset/audio/motion
afterward — the stale render was never re-validated. Fixed with
`_is_completed_run_stale`: compares `Project.updated_at` (already bumped by
every `update_project_beat_plan` call, no new column needed) against the
run's own `completed_at`. A later, independent edit now starts a genuinely
new run on the next "Create & Produce"; the run's *own* in-flight
assignment writes (which happen before its own completion) never
self-invalidate. This is the concrete mechanism behind the brief's Beat→
Visual→Quality→Render dependency graph — no separate "STALE" flag per
stage was needed since every real pipeline pass already re-derives
Visual/Quality live from current project state; only the *terminal*
COMPLETED-reuse shortcut needed this check.

## Recovery

Startup reconciliation (unchanged control flow, now also settles
checkpoints) treats every `FactoryRun` still active at process start as
interrupted by definition — there is no persisted worker for a factory run
in this single-process desktop app, so "found active at boot" can only mean
the previous process died. `RENDERING`/`QUEUED` runs still reconcile against
the linked `VideoComposeJob` first (unchanged from Task 18); the matching
`QUEUED`/`RENDERING` checkpoints are force-settled to match.

## Tests

18 new tests (`tests/api/test_factory_reliability.py`): checkpoint trail
for a full local run and a blocked run, crash recovery at each stage
(GENERATING_BEATS/ASSIGNING_ASSETS/QUALITY_CHECK/QUEUED/RENDERING, each
confirming no Beat regeneration on retry), reconciliation idempotency (no
duplicate checkpoint rows across two reconcile passes or repeated
retries), stale-COMPLETED invalidation (unit + a real end-to-end
re-render), attempt increment + the informational max-attempts flag, the
full error-classification table, and render-reconciliation checkpoint
settlement (completed/failed). `tests/api/test_factory_pipeline.py`'s own
harness extended with `FactoryCheckpoint.__table__`; all 21 of its
existing tests still pass unmodified otherwise. Full suite: 603/603
passing (one pre-existing, unrelated flake in `test_batch_render.py`
confirmed present on a clean checkout too, untouched by this task).

## Migration

`factory_run.attempt` added via `db/migrate.py`'s existing additive-column
convention (`ALTER TABLE ... DEFAULT 1`, so real existing rows backfill to
a real attempt count, not NULL). `factory_checkpoint` is a brand-new table,
created by the existing `Base.metadata.create_all()` with no migration
entry needed. Verified against the real `backend/data/library.db`.

## Problems

No frontend changes in this pass — Task 18's UI doesn't yet surface
`failed_stage`/`error_code`/attempt/checkpoints at all, so the new fields
are backend-only for now (`GET /factory-runs/{id}/checkpoints` is wired
and ready). Stale-RUNNING detection uses a fixed "any active run found at
boot is interrupted" rule rather than a time threshold, per this app's own
documented single-process architecture (see Task 18's own
`factory_pipeline.py` docstring) — correct here, but would need revisiting
if a persistent background worker across restarts were ever introduced.

## Cost

External API calls: 0. External cost: $0.

## Architecture

SQLite remains the sole source of truth. `FactoryCheckpoint` is the only
new table, owned entirely by `app.modules.factory`, no cross-module
imports. Existing `RenderJob`/`LocalRenderQueue` reused unchanged as the
one render pipeline. No Redis/Celery/RabbitMQ, no second workflow engine,
no new large payloads in SQLite.

## Next task

Task 20 — Factory Batch Engine: Parallel Production with Safe Concurrency
Limits.
