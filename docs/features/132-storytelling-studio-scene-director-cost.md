# 132. AI Storytelling Studio — Phase 3 (Scene Director wiring + cost guard)

The first thing in the Studio plan that touches real rows. New composition
root `app/api/v1/endpoints/story_pipeline.py` wires the Phase 0 pure
modules (`scene_director`, `ai.cost_estimator`) to the Phase 1 `story`
tables. **Still no generation** — this classifies and estimates only.

## What it does

- `POST /stories/{id}/classify-scenes` — runs the deterministic Scene
  Director over every `StoryScene`, persists the 4 sub-scores + composite
  + the `STILL` / `STILL_WITH_MOTION` / `AI_VIDEO` decision and a
  `motion_preset` hint. A scene a human froze (`visual_mode_source ==
  "USER"`) keeps its mode — only its scores are refreshed. `reason` lines
  and the AI_VIDEO budget (ratio + hard cap) come straight from the pure
  module.
- `GET /stories/{id}/config` — validates the `Story.project_config_json`
  blob against `app.modules.beat.schemas.ProjectConfig` (the piece
  feature 131 deliberately left opaque) and returns the normalised object;
  a bad blob is a 400, not a 500.
- `GET /stories/{id}/cost-estimate` — a conservative pre-flight
  `CostEstimate` for producing the story (LLM planning buckets + one image
  per non-reused still + AI-video seconds + TTS words) plus a **CostGuard
  verdict**: `OK` / `WARN` / `BLOCK` / `UNKNOWN`. The cap is
  `cost_guard.max_total_usd`, falling back to `Story.budget_usd`.
- `GET /stories/{id}/scene-plan` — read-only: every scene with its current
  scores/mode + the cost estimate, shaped for a future Studio UI.

## Key files

- **New:** `app/api/v1/endpoints/story_pipeline.py`,
  `tests/api/test_story_pipeline.py`
- **Modified:** `app/modules/story/service.py` (+`get_chapters_with_scenes`,
  `apply_scene_updates` — one-session bulk read/write for the stage),
  `app/api/v1/router.py` (mount)

## Non-obvious decisions

- **Composition root, not a module.** `story` never imports `beat`;
  `scene_director` / `ai` never import `beat`. `story_pipeline.py` is the
  one place allowed to hold all three — the same split `quality_gate.py`
  already uses. `ProjectConfig` → `SceneDirectorConfig` is a hand
  translation across the boundary, not an import.
- **The AI_VIDEO budget rounds to zero on small stories.** `round(0.15 *
  N)` is 0 for `N < 4`, so a 2–3 scene story gets no AI_VIDEO at all
  unless `ai_video_max_ratio` is raised. Correct (audio-first, video is
  the exception) but surprising — the tests pin it.
- **`video_usd` is `0.0`, not `None`.** The `null` video provider is
  genuinely priced at $0 in the Phase 0 table, so a story with AI_VIDEO
  scenes still gets a real grand total today; a real provider (Phase 10)
  flips the unpriced components to `None` + a note.
- **Cost estimate is not persisted.** It is pure/recomputable; caching it
  on `StoryRun.est_cost_json` waits for the actual run pipeline (Phase 4/5).

## Verification

175 targeted tests pass (`tests/modules/{story,scene_director,ai,beat}` +
`tests/api/test_story_pipeline`). Real `uvicorn` boot against a fresh DB:
full flow over HTTP — create story → chapter → 2 scenes → classify (battle
scene → `AI_VIDEO` mv 100, silent-dread reveal → `STILL_WITH_MOTION`) →
cost-estimate (`$0.24`, verdict `OK`) → scene-plan → bad-config PATCH then
`GET /config` → 400. Pre-existing unrelated failure:
`test_batch_render.py::RetryTests::test_retry_of_failed_item_with_no_beats_retriggers_beat_generation`
(fails on pristine `main` too).

## Landed in

`93480c4`
