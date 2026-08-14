# 43 — Production Dashboard: Factory Control Center

**Commit:** _(fill in after commit)_

Repurposes the previously-unbuilt `/dashboard` landing page (4 hardcoded
zero-value stat cards for the old Library app) into a real production
control center for the Video Factory: KPI counts, current batch progress,
live "Currently Rendering" panel, Needs Attention list, render queue,
recent videos/failures, a compact pipeline breakdown, and a $0 external
video-generation cost summary. A single `GET /dashboard` aggregates
everything in one call.

## Non-obvious decisions

- **Scope is "Projects reachable through a BatchItem" only** — there is
  no `GET /projects` list anywhere in this codebase, so a global "all
  projects" view isn't a real, listable thing. The classic singleton
  `beats.json` single-project flow is correspondingly out of scope.
- **`build_dashboard` is a plain function** (not just an HTTP handler) in
  a new composition root `app/api/v1/endpoints/dashboard.py` — the
  "DashboardService" the brief asked for, following the exact shape
  `quality_gate.run_quality_check` already established. It aggregates
  `app.modules.batch`/`beat`/`asset`/`video_composer` (none of which may
  import each other); no new `app/modules/dashboard/` was created since
  this owns no table or domain rule of its own.
- **READY/NEEDS_REVIEW/BLOCKED counts re-run the live Quality Gate** on
  every `BEATS_READY`/`NEEDS_REVIEW` item (same scope
  `batch_render.check_batch_quality` already uses) — never a stored,
  potentially-stale status column, matching Task 16's own "always live"
  philosophy. A fixed-asset project shows up as READY on the very next
  dashboard load even though its raw `BatchItem.status` is still
  literally `NEEDS_REVIEW` until a batch resync/retry happens.
- **Real bug fixed during testing**: SQLite doesn't actually persist
  tzinfo on a `DateTime(timezone=True)` column — a value round-tripped
  through the DB comes back naive, so subtracting it from
  `datetime.now(timezone.utc)` for the "Currently Rendering" elapsed time
  raised `TypeError`. Fixed with a small `_as_utc()` normalizer.
- **Polling, not the existing `EventBus`** — `app.core.events.EventBus`
  (used by `VideoComposerService` to publish `render.job.*` events) has
  no bridge to the frontend at all (no WebSocket/SSE endpoint exists
  anywhere in this codebase); building one wasn't justified when polling
  already works everywhere else (`HistoryPage`, `BatchDetailPage`). 3s
  while something is rendering/queued, 15s otherwise.
- **"Production Pipeline" reports real `BatchItemStatus` counts**, not
  the brief's own illustrative per-stage ready/review split — this app's
  Quality Gate is one review point covering visuals/motion/audio/pacing
  together, not staged per dimension, so a fabricated per-stage split
  would misrepresent real state.
- **"New Batch" deep-links to `/batches?new=1`** — a small, additive
  `useSearchParams` read in the existing `BatchPage.tsx` opens the exact
  same creation modal already there; no duplicated creation flow.

## Tests

13 new backend tests (`tests/api/test_dashboard.py`): empty state, the
brief's own literal "12 projects: 6 READY/2 NEEDS_REVIEW/1 BLOCKED/1
RUNNING/2 COMPLETED" fixture, its own "Batch A: 10 projects" fixture,
current-render phase/progress/elapsed, queue ordering, attention priority
ordering + 5-item limit, recent videos/failures. Full suite: 564/564
passing. Frontend `tsc --noEmit`: 0 errors.

## Manual verification (real, live dev server + Playwright)

Built a real 5-project batch via the live API/DB (`batch_id=4`) landing
in exactly 2 READY / 1 NEEDS_REVIEW / 1 BLOCKED / 1 RENDERING, confirmed
via a live dashboard screenshot that every KPI and the Needs Attention
list matched. Then ran the full real UX flow through the browser:
clicked **Review** on the NEEDS_REVIEW item → landed on the exact project
→ swapped the mismatched asset for a well-matched one via the real Asset
Browser → saved → back on the Dashboard, ready count rose 2→3 and the
item dropped out of Needs Attention. Clicked **Render Video** on that
now-READY project → Quality Gate passed with zero friction → a
follow-up render (5-beat project, real ~30s render) was caught live via
screenshot mid-flight, correctly showing **Currently Rendering**
(phase `BUILD_AUDIO`, beat 5/5, elapsed 27.5s) and **Render Queue**
(one `RUNNING` + one `QUEUED`) — then confirmed the transition to
COMPLETED (`rendering` 1→0, `completed_today` 12→13, both jobs appearing
in Recent Videos with real render times).

## Performance

`GET /dashboard` responded well under 500ms throughout manual testing
against the live dev DB (which has accumulated real data across 4
batches / 25 render jobs from this session's own prior tasks) — no
video probing/thumbnailing/asset scanning happens on this path, only
DB queries plus the existing Quality Gate's own already-cheap analysis.

## Cost

External video-generation API calls: 0. External video-generation cost:
$0 (hardcoded real fact — this pipeline has no such integration at all).
AI *content* generation (Beat text via Claude) is deliberately not
reported: `app.modules.ai.history.AIGenerationHistory` requires a
Library `video_id`, which Beat/Project rows don't have, so there's no
real, timestamped source to compute "today's AI calls" from honestly.

## Problems

- `current_batch.status_counts` reflects the raw `BatchItem.status`
  column, which can lag behind reality until something calls
  `sync_batch`/`get_batch_detail`/`retry_batch` (a pre-existing Task 13
  characteristic) — observed live (a completed render's item stayed
  "RENDERING" in that one breakdown until an explicit sync), while every
  other dashboard number (KPIs, current render, queue, recent videos)
  reads `VideoComposeJob` directly and is always fresh.
- A `NEEDS_REVIEW` batch item has no resync path back to `BEATS_READY`
  (existing `retry_batch` only handles `FAILED`/`SKIPPED`) — fixing its
  asset makes the dashboard correctly show it as READY, but "Render All"
  on the batch page still won't pick it up; rendering it requires the
  single-project Render step instead. Pre-existing Task 16 gap, out of
  this task's scope to fix.

## Architecture

Existing `Batch`/`BatchItem`/`Project`/`VideoComposeJob` tables reused
(no new table). Existing Quality Gate reused (no second quality engine).
Existing `VideoComposerService`/render queue reused for Cancel/Retry (no
new queue). No analytics system, no Redis/Celery, no WebSocket
infrastructure, no fake metrics, no module-to-module imports —
`app/api/v1/endpoints/dashboard.py` is the one place allowed to know
about `batch`/`beat`/`asset`/`video_composer` together.

## Next task

Task 18 — One-Click Factory Pipeline: Script → Beat → Visual → Quality →
Render.
