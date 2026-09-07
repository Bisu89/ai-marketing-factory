# 130. AI Storytelling Studio — Phase 0 (Foundation)

First increment of the "AI Storytelling Studio" plan (published architecture
doc, artifact `e48d073f`). Pure scaffolding — **no behaviour change, no new
DB table, no wiring into the render pipeline**. These are the interfaces and
pure engines that Phase 1–5 plug into.

## What it does and why

- **AI Scene Director** — `app/modules/scene_director/` — a pure,
  deterministic classifier (mirrors `app/modules/quality/analyzer.py`'s
  "no I/O, no cross-module import" shape). `classify_scenes(scenes, config)`
  scores each scene on importance / movement / emotion / complexity and
  picks `STILL` / `STILL_WITH_MOTION` / `AI_VIDEO`, then enforces an
  AI-video budget (ratio + hard cap), demoting the lowest-scoring video
  candidates to motion. **Audio-first by construction:** emotional
  intensity alone never triggers `AI_VIDEO` — only real on-screen movement
  (verb list) does. A tearful reveal is a `STILL_WITH_MOTION` close-up, a
  cavalry charge is `AI_VIDEO`.
- **Video provider abstraction** — `app/modules/ai/video_client.py` —
  `VideoProvider` protocol + `NullVideoProvider` (the only one wired;
  `is_available()` → `False`, `generate()` raises `VideoGenError`). The
  future AI_VIDEO stage checks `is_available()` and degrades to
  `STILL_WITH_MOTION`. Sibling of `image_client.py`; always its own
  provider choice, independent of `settings.ai_provider`.
- **Model routing** — `app/modules/ai/model_router.py` — `route(task_kind,
  provider)` → tier (`cheap`/`standard`/`premium`) + token headroom. Every
  task kind is mapped; Phase 0 has no cheap/premium models configured yet
  so `.model` is always `None` ("use provider default"). Wiring into real
  LLM calls is Phase 4 — plan estimates 40–60% LLM cost saved.
- **Cost estimator** — `app/modules/ai/cost_estimator.py` —
  `estimate_story(CostEstimateInput)` → `CostEstimate` with per-component
  breakdown + `per_extra_language_usd` marginal. Conservative (prices every
  LLM call at the default model). Follows the "null + why, never a
  fabricated $0" convention: an unpriced video provider → `video_usd` and
  `total_usd` are `None` with a note. Localization marginal excludes
  images/video/research (generated once, shared).
- **Video pricing table** — `app/modules/ai/pricing.py` — `VIDEO_PRICE_TABLE`
  + `video_cost_usd(provider, seconds)`. Only `null` (→ $0) is priced;
  real providers get filled in Phase 10.
- **Six additive `ProjectConfig` sub-configs** — `app/modules/beat/schemas.py`
  — `scene_classification`, `visual_density`, `cost_guard`, `model_routing`,
  `ai_disclosure`, `story_compile`. All `default_factory`, so every
  pre-Phase-0 `beats.json` / `beat_plan_json` / `templates.json` parses
  unchanged (same backward-compat pattern as features 12/21/59). Nothing
  consumes them yet.

## Key files touched

- **New:** `backend/app/modules/scene_director/{__init__,schemas,classifier}.py`,
  `backend/app/modules/ai/{video_client,model_router,cost_estimator}.py`
- **Modified (additive only):** `backend/app/modules/ai/pricing.py`,
  `backend/app/modules/beat/schemas.py`
- **Tests:** `backend/tests/modules/scene_director/test_classifier.py`,
  `backend/tests/modules/ai/{test_model_router,test_cost_estimator,test_video_client}.py`,
  + `StorytellingStudioSubConfigTests` in `tests/modules/beat/test_schemas.py`
- **Test updated for the new fields:**
  `tests/modules/beat/test_templates.py::test_project_config_never_contains_project_specific_identifiers`
  (the six new sub-configs are plain scalars — the "no project-specific IDs
  in a template config" invariant still holds, so the expected field set
  was extended)

## Non-obvious decisions

- `SceneClassificationProjectConfig` (on `ProjectConfig`) **duplicates**
  `scene_director.SceneDirectorConfig` field-for-field rather than importing
  it — the module-isolation rule (`app/modules/README.md`) plus the same
  "duplicate the small contract across the boundary" convention
  `quality_gate.py` already uses to build a `QualityAnalysisInput` from a
  `ProjectConfig`.
- Scene Director does **not** compute cost — that needs pricing and belongs
  to `cost_estimator` (in `app/modules/ai/`), which consumes the Director's
  output. Clean one-way dependency.
- The AI-video budget demotion is **deterministic**: ties broken by scene
  order (earlier scene keeps its video slot).

## Landed in

`TBD` — `pytest tests/modules/` + factory/batch regression green;
`app.main` boots.
