# 46 — Factory Batch Engine: Parallel Production with Safe Concurrency Limits

**Commit:** _(fill in after commit)_

Adds real, bounded concurrency to Task 18/19's `FactoryRun`-per-project
batch orchestration: `settings.max_parallel_projects` (default 2) caps how
many projects progress through Beat/Visual/Quality at once, while the
existing render queue stays exactly as serial as it already was. No new
queue, worker, pipeline, or Batch model — extends `Batch`/`BatchItem`
(Task 13) and `factory_pipeline.py`'s existing `run_batch_factory`/
`continue_batch_factory` (Task 18) in place.

## The gap this closes

Task 18's `run_batch_factory` already existed but had three real problems:
it sized its `ThreadPoolExecutor` off `max_concurrent_ai_generation` (an AI
rate limit, not a project-concurrency knob), it ran **synchronously inside
the HTTP request** (`POST /batches/{id}/factory-run` blocked until every
project's local stages finished), and it never wrote back to
`BatchItem.status` at all — so `Batch.status` (derived from `BatchItem`
statuses) stayed stale for any batch produced through the factory flow.

## Two independent concurrency limits

```
max_parallel_projects (default 2)  -- a plain ThreadPoolExecutor around
                                       _run_batch_item; its own internal
                                       work queue is the FIFO scheduler,
                                       no custom one was built
max_parallel_renders  (default 1)  -- informational only; VideoComposerService
                                       has exactly one queue.Queue + one
                                       worker thread (unchanged) -- already
                                       serial by construction
max_concurrent_ai_generation (2)   -- unchanged (Task 13), now additionally
                                       enforced process-wide by a new
                                       app.core.concurrency.ai_generation_semaphore
                                       shared between the old script-based
                                       batch flow and the new engine
```

A project's `ThreadPoolExecutor` slot frees the instant its own
`_stage_render` hands off to the existing `LocalRenderQueue` (non-blocking,
Task 18) — not when the render finishes — so `max_parallel_projects`
naturally gives the single-worker render queue a small prep buffer ahead
of it (the brief's own "render queue buffer" concept) without any explicit
buffering logic.

## BatchItem ↔ FactoryRun sync

New `BatchItem.status = "RUNNING"` covers every FactoryRun stage from
`PREPARING` through `RENDERING` as one bucket (`_sync_batch_item_from_run`);
NEEDS_REVIEW/FAILED/CANCELLED/COMPLETED/READY_TO_RENDER map through
directly. Two sync points: synchronously right after `_execute_pipeline_sync`
returns (covers everything except an in-flight render), and from the
existing `render.job.*` event handlers (Task 18) for the async render tail
— reusing the same `EventBus`, no new events needed.

## Atomic claim

`batch_service.claim_item` is a single `UPDATE ... WHERE status IN (...)`,
not a read-then-write — `rowcount == 1` is the only way a caller knows it
won the claim. Used by the normal scheduling pass (`PENDING`/
`PROJECT_CREATED`/`BEATS_READY`/`READY_TO_RENDER` → `RUNNING`), by
"Continue Ready" (`NEEDS_REVIEW` → `RUNNING`), by "Retry Failed" (`FAILED`
→ `RUNNING`), and by Skip (→ `SKIPPED`) — one primitive, four callers.
`bulk_cancel_claimable_items` is the same idea for Cancel: one atomic
bulk `UPDATE`, so a concurrently-running claim can only ever lose the race,
never sneak a start in after cancellation.

## Pause / Resume / Cancel

- **Pause**: sets a per-batch `threading.Event` (mirrors Task 18's own
  per-run `_cancel_events`) checked at the very top of each item's worker
  function, before it claims anything — an item already claimed/running
  finishes normally. `Batch.status → "PAUSED"` immediately (not waiting for
  in-flight work), matching "pause means stop starting new work," not
  "stop everything right now."
- **Resume**: clears the event, re-invokes the same `run_batch_factory`
  core — it naturally only picks up items still in a claimable status.
- **Cancel**: every still-claimable item → `CANCELLED` atomically; every
  `RUNNING` item's FactoryRun gets a real cancellation request through the
  existing `cancel_run` (Task 18) — never force-killed. Already-COMPLETED
  items are untouched.

## Restart recovery

New `reconcile_batches_on_startup()` (`main.py`, after Task 19's
`reconcile_factory_runs_on_startup`, which must settle every FactoryRun
first): every `Batch` still `"PROCESSING"` → `"PAUSED_AFTER_RESTART"`;
every `"RUNNING"` `BatchItem` syncs from its now-interrupted FactoryRun.
Never auto-resumes — an explicit "Resume Batch" is always required (same
reasoning as Task 19's single-run recovery: source drives may be
unmounted, credentials may have changed, the user may be mid-task).

## New/changed statuses

`BATCH_STATUSES` +`PAUSED`/+`PAUSED_AFTER_RESTART` (8 total);
`BATCH_ITEM_STATUSES` +`RUNNING` (11 total) — the old script-based flow
(`batch_render.py`, untouched) never sets `RUNNING`, so a batch's items
never mix the two flows' own in-flight markers. `recompute_batch_status`
now treats `RUNNING` the same as the old flow's `RENDERING` (both mean
"actively in flight").

## Real gap found and fixed: eligibility was too permissive

Task 18's original `run_batch_factory` would silently re-attempt a `FAILED`
item on every call (nothing excluded it), effectively auto-retrying
without the user asking. `claim_item`'s `BATCH_ITEM_ENGINE_CLAIMABLE_STATUSES`
now excludes `FAILED`/`NEEDS_REVIEW`/every terminal status — those only
ever restart through the new, separate `retry_batch_failed`/
`continue_batch_factory` actions (matching the brief's own distinct
"[Retry Failed]"/"[Continue Ready]" buttons).

## Endpoints

`POST /batches/{id}/factory-run` and `/factory-continue` (existing routes,
Task 18) are now non-blocking — they return immediately (`runs_started`/
`runs_processed` always 0, since nothing has settled yet; the frontend
already polls `GET /batches/{id}` afterward and never used those numbers,
see `frontend/src/pages/BatchDetailPage.tsx`'s own `handleProduce`). New:
`/factory-retry-failed`, `/factory-pause`, `/factory-resume`,
`/factory-cancel`, `/batches/{id}/items/{item_id}/skip`.

## Frontend

No new pause/resume/cancel/retry-failed UI in this pass (out of scope,
same "backend-first" precedent as Task 19) — but `types/batch.ts` and
`BatchDetailPage.tsx`'s exhaustive `Record<BatchStatus/BatchItemStatus,
string>` label maps *were* updated (TypeScript enforces completeness on
these), since `reconcile_batches_on_startup` can now write
`PAUSED_AFTER_RESTART`/`RUNNING` into a batch this page already polls via
the existing `GET /batches/{id}` — leaving those unmapped would have shown
a broken/blank label after a real app restart, a genuine regression this
task's own new code could trigger, not a hypothetical one. `tsc --noEmit`:
0 errors.

## Tests

15 new (`tests/api/test_batch_factory_engine.py`): concurrency bound
(2 projects max, using a real-time-slept instrumented fake so the test
proves actual overlap, not accidental serialization), FIFO order under
full serialization, structural render-concurrency (one worker thread),
50-project stress test, AI semaphore bound + real wiring into
`_stage_generate_beats` (reading the semaphore's own internal counter,
since `threading.Semaphore` binds `__enter__ = acquire` at class-definition
time — patching the instance's `.acquire` silently doesn't intercept
`with sem:`, a real gotcha hit and fixed while writing this), NEEDS_REVIEW/
FAILED isolation (real Quality Gate outcomes, not faked), pause (running
item finishes, rest stay unclaimed), resume (only continues what was
pending), cancel (completed preserved, pending cancelled), restart
recovery, and idempotency (running a batch twice creates no duplicate
FactoryRuns). `tests/api/test_factory_pipeline.py`'s own
`BatchIntegrationTests` updated for the split Continue/Retry-Failed
actions and BatchItem-status sync; all other existing tests unmodified.
Full suite: 618 tests, 616 passing outright; the remaining 2 tallies
(1 failure + 1 error) both trace to the same single pre-existing,
order-dependent flaky test in `test_batch_render.py`
(`test_retry_of_failed_item_with_no_beats_retriggers_beat_generation`,
already noted in Task 19's own doc) — confirmed still present with this
task's entire diff stashed out on a clean checkout, so unrelated to this
task. A second, separate pre-existing flake was also found and confirmed
this way (`test_dashboard.py`'s batch-ordering test, ~1-in-5 runs even in
isolation) but did not appear in this particular full-suite run.

## Test-isolation fix found along the way

`_batch_pause_events` (this task's own module-global, batch-id-keyed dict)
needed the exact same test-teardown cleanup Task 19 already added for
`_cancel_events` — each test gets a fresh DB whose ids restart from 1, so
a `PAUSED` batch's still-`.set()` event was leaking into the next test's
same-numbered batch and silently no-op'ing every item from the start.
Fixed in the shared `_FactoryTestCase.tearDown`.

## Manual verification

Not run live in this pass (no Anthropic key configured in this dev
environment for a real multi-project Beat-generation batch, matching
Task 18/19's own documented constraint) — verified instead via the
instrumented-fake concurrency tests above (real `threading`/
`ThreadPoolExecutor`, real DB, only `_execute_pipeline_sync` faked) plus
the NEEDS_REVIEW/FAILED isolation and idempotency tests, which exercise
the real single-project pipeline end-to-end against real local assets.

## Performance

Not benchmarked against a real multi-project batch with real Claude/ffmpeg
in this environment (see above). The 50-project stress test (fake,
10ms/project) completes in well under a second and holds peak concurrency
at exactly `max_parallel_projects`.

## Cost

New external APIs: 0. New external cost: $0. Beat generation still uses
the existing Claude integration (Task 13/18) at its existing, unchanged
per-call cost — this task only adds a concurrency *limiter* around it,
never a new call site.

## Problems

No frontend pause/resume/cancel/retry-failed/skip UI — only the existing
labels were kept from breaking (see "Frontend" above). `max_parallel_renders`
is reporting-only; making it actually control render concurrency would
require multi-worker changes to `VideoComposerService` explicitly out of
this task's scope (section 4/11: "if the existing renderer is already
strictly serial, keep it serial"). The old script-based batch flow
(`batch_render.py`) and the new Factory Batch Engine remain two separate,
un-unified orchestration paths for the same `Batch`/`BatchItem` tables —
intentional (avoids rewriting/risking Task 13's own working flow) but
still two things to reason about long-term.

## Architecture

One `FactoryPipeline` (`_execute_pipeline_sync`, unchanged), one
`RenderQueue`/`RenderWorker` (`VideoComposerService`, unchanged), one
`Batch`/`BatchItem` model (extended, not duplicated). Concurrency limits
enforced via plain `concurrent.futures.ThreadPoolExecutor` +
`threading.Event`/`threading.Semaphore` + atomic SQL `UPDATE`s — no
Celery/Redis/RabbitMQ/distributed locks/generic scheduler framework. No
module-to-module imports: the engine lives entirely in the existing
`factory_pipeline.py`/`batch_render.py` composition roots plus
`app.core.concurrency` (core infra, not a domain module).

## Next task

Task 21 — Factory Asset Strategy: Build a Reusable Local Visual Pack System.
