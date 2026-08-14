# 44 — One-Click Factory Pipeline: Script → Beat → Visual → Quality → Render

**Commit:** `d202837`

The orchestration layer that connects everything built in Tasks 12-17 into
one "Create & Produce" action: generate/reuse Beats, auto-assign visual
assets, run the Quality Gate, and hand off to the existing render queue —
without implementing a second version of any of those systems.

```
Script → Beat (reuse/generate) → Visual (auto-assign) → Quality Gate → RenderJob → LocalRenderQueue → final.mp4
```

## Key finding: no separate "Visual Intent" stage exists

Beat generation (`beat_generate.py`, Claude) already produces
`visual_hint` per beat as part of the same call — there's no separate
AI step that generates it afterward. `PREPARING_VISUALS` is therefore a
real but instantaneous pass-through stage in this codebase, not a no-op
placeholder for a missing feature.

## New: FactoryRun

`app/modules/factory/` (pure, own table, zero cross-module imports) —
`status` holds one of 13 granular values directly (mirrors
`VideoComposeJob`'s own coarse-status/phase split, just collapsed to one
field since a FactoryRun's coarse status and current stage are the same
thing while active); `failed_stage` remembers where a FAILED run stopped,
for Retry. The actual orchestration (`run_project`-equivalent) lives in
the composition root `app/api/v1/endpoints/factory_pipeline.py`, which
is the one place allowed to import `factory`/`beat`/`asset`/`quality`/
`batch`/`video_composer` together — same shape as `batch_render.py`.

## Non-obvious decisions

- **Auto-assignment reuses `AssetService.search()` + Task 16's
  `compute_asset_confidence`** (both promoted from private to public for
  this cross-composition-root reuse) — still no real AssetMatcher exists
  in this codebase (same finding as Tasks 14/15/16); this is the
  deterministic stand-in, run in its natural "given a hint, find
  candidates" direction this time.
- **Manual assignment is untouched, always** — the assign stage only
  ever fills in `asset_id: None` beats; an already-assigned beat (manual
  or from an earlier run) is never revisited by auto-assign.
- **Factory review policy is layered on top of, not inside, the Quality
  Gate** — `ProjectConfig.factory` (new: `auto_assign_high_confidence`,
  `require_review_for_medium_confidence`, `require_review_for_low_confidence`,
  `render_after_quality_pass`) can escalate a Quality-Gate-READY result to
  factory-level NEEDS_REVIEW (MEDIUM confidence has no Quality Gate
  warning of its own — see Task 16's analyzer, untouched here), but can
  never override a Quality-Gate BLOCKED. Verified live: a real run scored
  `quality_status=READY, score=99` while the *factory* status was
  NEEDS_REVIEW, purely from this policy layer.
- **Continue re-evaluates confidence fresh from current state**, not a
  cached decision from the original ASSIGNING_ASSETS pass — verified
  live: reassigning an asset without updating its now-stale `visual_hint`
  correctly stayed NEEDS_REVIEW on Continue; only clearing the hint (or
  making it match) resolved it.
- **Idempotent by construction**: `create_run()` returns a project's
  already-active run unchanged (never two runs, DB-query-then-insert
  guarded by an in-process lock); a COMPLETED run is returned unchanged
  unless `force=true` is passed. Retry never regenerates Beats/re-assigns
  already-assigned assets — it just re-invokes the same idempotent
  pipeline from the top (each stage's own reuse-check does the rest),
  except a RENDERING-stage failure, which delegates straight to
  `VideoComposerService.retry_job()`.
- **Recovery**: on startup, after `VideoComposerService`'s own crash
  recovery has already settled every `VideoComposeJob`, any FactoryRun
  still in an active status is reconciled against its linked job
  (COMPLETED/FAILED/CANCELLED) or marked `FACTORY_INTERRUPTED` if it
  never reached a RenderJob at all.
- **Batch coordinator is not a second pipeline** — `run_batch_factory`/
  `continue_batch_factory` just call the same per-project pipeline
  function inside a `ThreadPoolExecutor(max_workers=settings.max_concurrent_ai_generation)`,
  the exact concurrency-bounding shape `_run_batch_beat_generation`
  already established.
- **Real bug found and fixed in the frontend**: `ProductionProgress`'s
  own render-job-ready handoff (`setJobId`+`setStep(5)`) could race ahead
  of `VideoFactoryPage`'s own project-load effect (local pipeline stages
  finish in tens of milliseconds), landing Step 5 on the page's still-
  empty initial state (0 beats). Fixed by gating `ProductionProgress`'s
  mount on a new `projectDataLoaded` flag set once the page's own load
  effect completes.

## Tests

21 new backend tests (`test_factory_pipeline.py`): state machine,
beat-reuse vs generate, auto-assign (including "manual never overwritten"
and "no candidate blocks"), review/resume (confirms no beat
regeneration), retry (asset-stage vs render-stage), idempotency
(duplicate-run reuse, force-vs-default), recovery/reconciliation (3
scenarios), a real end-to-end render, and a real 3-project batch with
mixed READY/NEEDS_REVIEW/FAILED outcomes. Full suite: 585/585 passing.
Frontend `tsc --noEmit`: 0 errors.

## Manual verification (real, live dev server + Playwright)

No Anthropic API key is configured in this dev environment, so
`GENERATING_BEATS` itself was verified via the automated suite (mocked)
plus its real, correct `BEAT_GENERATION_FAILED` failure path (no key →
immediate, clear error) — not a live Claude call. Everything downstream
of Beat generation was verified for real: created a project via the real
"New Video" modal, seeded 5 beats with only `visual_hint` text (zero
manual asset assignment), triggered the pipeline, and confirmed 5/5
beats were auto-assigned correctly, Quality Gate scored READY/100, a
real RenderJob was created and completed, and a real `video_hoan_chinh.mp4`
exists on disk. Separately reproduced NEEDS_REVIEW live (a MEDIUM-confidence
pre-assigned asset, Quality-Gate-READY but factory-paused) — the
"Production Paused" UI matched the brief's own mockup exactly — fixed it
through the real Beat editor, clicked **Continue Production**, and
confirmed it resumed straight from Quality Check (no beat regeneration)
into a real, live render (watched "Rendering Beat 1/3" in progress) that
completed successfully. Also confirmed idempotency live: a second
`factory-run` call reused the COMPLETED run untouched; `force=true`
started a genuinely new one.

## Cost

Video generation API calls: 0. Video generation cost: $0 (this pipeline
has no such integration — reused from Task 17's own dashboard framing).
Content generation (Beat text via Claude): 1 call when generation is
actually needed, cost unknown (provider doesn't report per-call cost);
never counted toward the $0 figure above.

## Problems

- No "Quick Produce" button was added for an *existing* project with a
  script but no beats yet (section 30 lists this as optional) — the only
  UI trigger for a factory run is "Create & Produce" at project creation
  time, or the batch-level Produce/Continue Batch buttons.
- The live "Production" checklist (PREPARING…QUALITY_CHECK) is visually
  real but has a narrow observation window in this local-only environment
  — local stages complete in tens of milliseconds when Beats already
  exist, so the banner is genuinely hard to catch mid-flight (confirmed
  via the automated suite's own explicit per-stage status assertions,
  and via the NEEDS_REVIEW scenario above, which stays visible since it
  pauses).

## Architecture

No new render pipeline, batch system, queue, quality engine, asset
matcher, Beat generator, or event bus. `app.modules.factory` has zero
cross-module imports; `app/api/v1/endpoints/factory_pipeline.py` is the
one composition root allowed to bridge `factory`/`beat`/`asset`/
`quality`/`batch`/`video_composer`. No Redis/Celery.

## Next task

Task 19 — Factory Reliability: Persistent Pipeline State, Checkpoints and
Crash-Safe Resume.
