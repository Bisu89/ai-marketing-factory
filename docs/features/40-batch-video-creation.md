# 40 — Batch Video Creation + Script Queue

**Commit:** _(fill in after commit)_

Turns Video Factory into a batch system: paste/upload N `---`-separated
scripts, pick one template, "Create" transactionally makes N `Project`
rows + a `Batch`/`BatchItem` per script. "Generate Beats" and "Render All"
are separate, explicit actions (never auto-triggered). Batch rendering
reuses the *existing* single-worker render queue (Task 8/11) — no second
queue/worker/pipeline.

## Key architectural finding

This codebase had no multi-project store (Task 12 already found this) —
the whole app worked against one singleton `beats.json`. Batch is the
first task that genuinely needs many independently-addressable projects
at once, so a real `Project` table (`app/modules/beat/models.py`) was
added as new, necessary infrastructure. The singleton `beats.json`
GET/PUT is untouched; Projects are a parallel system.

## Non-obvious decisions

- **Atomic batch creation**: `app.modules.beat`/`app.modules.batch` each
  use their own per-call DB session (so a background thread can use them
  independently) — can't provide cross-table atomicity if called in
  sequence. `create_batch()` in the composition root
  (`app/api/v1/endpoints/batch_render.py`) is the one place that opens a
  single shared session and builds `Project`+`Batch`+`BatchItem` rows
  directly, committing once.
- **Render eligibility is computed, not stored** — `READY_TO_RENDER` from
  the status vocabulary is never a literal transition; a `BEATS_READY`
  item's eligibility is recomputed fresh on every `GET /batches/{id}` by
  attempting to build its `CompositionPlan` (missing/invalid asset →
  ineligible, surfaced via `eligible`/`ineligible_reason`).
- **Bounded AI concurrency**: a plain `ThreadPoolExecutor(max_workers=
  settings.max_concurrent_ai_generation)` inside one background thread per
  "Generate Beats" call — not a persistent worker.
- Beat→Scene conversion for server-side batch rendering
  (`_project_composition_plan` in `batch_render.py`) reuses the existing
  `app.modules.motion.service.build_motion_plan` and
  `app.core.render_profile.get_render_profile` rather than re-deriving
  numeric motion defaults in Python.

## Tests

422 backend tests passing (up from 386). New: 16 parser tests, 9 batch
creation tests (incl. transactional rollback), 3 beat-generation/
concurrency tests, 4 render-queue integration tests (real ffmpeg, real
single-worker queue, one failure doesn't block the rest, cancel), 3 retry
tests, 1 full 5-script→5-project→5-real-`final.mp4` end-to-end test.
Frontend `tsc --noEmit` clean.

## Manual verification (real, not simulated)

Real backend+frontend dev servers, driven with Playwright. Batch 1: 5
scripts created via the real UI wizard → beat plans authored via the real
`PUT /projects/{id}/beat-plan` (no Anthropic key in this dev environment,
so `Generate Beats` was also exercised for real and correctly failed each
item cleanly with `"Anthropic API key not configured..."`, batch status
`FAILED`, without crashing) → `Retry Failed/Skipped` → all 5 rendered
through the real queue → 5 real `final.mp4` files confirmed via `ffprobe`
(h264/aac) with `external_api_calls: 0` / `external_api_cost_estimate: 0`
in every real `report.json`. Also opened one batch project via
`/video-factory?project=<id>` in the real UI and confirmed the beat
editor loads that project's real data with a working "Back to Batch"
link. Batch 2: same flow with one project pointed at a deliberately
corrupt image — result: 4 `COMPLETED`, 1 `FAILED` with a real ffmpeg
error message, batch status `PARTIAL_FAILURE`, other 4 unaffected.

## Cost

Video rendering: `external_api_calls: 0` / `$0` for all 9 real renders
across both manual-verification batches (local narration). AI beat
generation cost is tracked separately and was never fabricated — this
dev environment has no Anthropic key configured, and that failure surfaced
honestly rather than being papered over.

## Next task

Task 14 — Asset Automation: Beat → Visual Asset Assignment with
Local-First Strategy.
