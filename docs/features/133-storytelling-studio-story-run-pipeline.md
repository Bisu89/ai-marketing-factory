# 133. AI Storytelling Studio — Phase 4 (resumable STORY_PLAN run)

The first pipeline in the Studio. A `StoryRun` walks a fixed stage list
from a bare idea to a fully broken-down, scene-classified, cost-checked
story — crash-safe and idempotent, a 1:1 mirror of the Factory's
`FactoryRun` / `FactoryCheckpoint` machinery.

## Stages (scope `STORY_PLAN`)

```
STORY_DEVELOPMENT → STORY_BIBLE → CHARACTER_BIBLE → CHAPTER_OUTLINE
  → SCENE_BREAKDOWN → SCENE_CLASSIFICATION → READY
```

- **The five LLM stages** (`story_stages.py`) each: check for their own
  output first and no-op if it exists (reuse, don't regenerate — same as
  `factory_stages._stage_generate_beats`), route the call through
  `model_router.route(task_kind, provider)` (tier → token headroom, and a
  real model id once `TIER_MODEL_MAP` is filled), validate the structured
  output, then persist. `STORY_BIBLE` also spawns `StoryLocation` rows;
  `CHARACTER_BIBLE` spawns `StoryCharacter` rows with a locked
  `canonical_prompt_block`; `SCENE_BREAKDOWN` resolves the model's
  character/location *names* back to real row ids per chapter.
- **`SCENE_CLASSIFICATION`** is deterministic: Phase 3's
  `classify_and_persist` + `estimate_cost`. A `BLOCK` cost-guard verdict
  pauses the run at `NEEDS_REVIEW` (never `FAILED`) with
  `error_code = "COST_GUARD_BLOCKED"`; the user raises the cap / trims the
  story and retries. `OK` / `WARN` / `UNKNOWN` → `READY`, and
  `Story.status` advances to `SCENES_READY`.

## Endpoints

- `POST /stories/{id}/runs` — start (or return the already-active run).
  Background thread; poll `GET /story-runs/{id}` + `/checkpoints`.
- `POST /story-runs/{id}/retry` — a `FAILED` **or** cost-guard-paused
  (`NEEDS_REVIEW`) run. Replays from the top; every stage's reuse check
  makes finished work free, so it resumes from the first incomplete stage
  (same design as `factory_pipeline.retry_run`).
- `POST /story-runs/{id}/cancel` — cooperative; the thread stops at the
  next stage boundary.

## Key files

- **New:** `app/api/v1/endpoints/story_stages.py` (stage workers + prompts
  + JSON schemas + `StoryStageError`), `tests/api/test_story_run_pipeline.py`
- **Modified:** `app/api/v1/endpoints/story_pipeline.py` (orchestration:
  `_execute_story_plan_sync`, `create_and_start_run`, `retry_run`,
  `cancel_run`, 3 routes), `app/modules/story/service.py` (the run +
  checkpoint helpers mirroring `factory.service`, `bulk_add_*`,
  `merge_story_json`, `mark_run_failed`; `reconcile_story_runs_on_startup`
  now also settles a stuck `RUNNING` checkpoint),
  `app/modules/ai/llm_client.py` (`call_structured` gains an optional
  `model` override — additive, every existing caller unaffected)

## Non-obvious decisions

- **`model_router` is wired, but `call_structured` still uses the provider
  default model** until `TIER_MODEL_MAP` gets a real cheap/premium entry
  (a one-line change). What Phase 4 delivers today: every LLM call goes
  through `route()`, the tier sets the token headroom, and `decision.note`
  is logged. The `model` plumbing through `llm_client` is done so filling
  the map is the only remaining step.
- **Retry replays from the top, not from `failed_stage`.** Idempotency
  (each stage's "already have output?" check) makes this equivalent to a
  resume, without a second resume-logic path. A cost-guard `NEEDS_REVIEW`
  retry re-runs only the deterministic classification + re-checks the
  guard — the LLM stages all no-op.
- **No persisted worker.** A run still in an active status at process
  start was interrupted — `reconcile_story_runs_on_startup` (already wired
  into `main.py` since Phase 1) marks it `FAILED` + settles its checkpoint.

## Verification

9 pipeline tests + 10 Phase 3 tests + 819 `tests/modules` + factory/series
regression all pass. Real `uvicorn` HTTP smoke: `POST /stories/1/runs` →
routes through `model_router` (log line confirms), calls OpenAI, a 401
(invalid key) → run `FAILED` / `failed_stage=STORY_DEVELOPMENT` /
checkpoint `FAILED`; `POST /retry` → `200`, `attempt=2`, fails cleanly
again; `cancel` on a terminal run → `200` no-op.

## Landed in

`TBD`
