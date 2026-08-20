# 75. AI Cost Tracking

**Commit:** `b245c67`

Observability/cost-accounting only, per this task's own instruction --
no generation behavior changed, no revenue.

## Pricing abstraction

`app/modules/ai/pricing.py` -- a small provider/model/input-price/
output-price/effective-date table (`PRICE_TABLE`), the one place a
$/token rate lives (generalizes the same "single named constant" shape
`llm_client.py`'s `ANTHROPIC_MODEL`/`OPENAI_MODEL` and `image_client.py`'s
`IMAGE_COST_USD` already use). `price_for()` picks the latest entry with
`effective_from <= call.created_at`, so re-pricing a model later never
rewrites the cost of calls already billed at the old rate.

Neither `claude-sonnet-5` nor `gpt-5.6-luna` has a real, confirmed
pricing page this codebase can check today -- per explicit user
direction, both are seeded with rough reference estimates
(`confirmed=False`) instead of being left blank, so the dashboard has
real numbers from day one. The UI shows a visible warning banner
whenever any priced group includes an unconfirmed rate. Update the two
entries in `pricing.py` with the real negotiated/published rate once
known -- nowhere else needs to change.

Cost is always computed live from `ai_generation_history`'s existing
`input_tokens`/`output_tokens` columns -- never duplicated or cached.
When pricing isn't configured or token counts are missing, cost is
`null` + an explanatory note, never a guessed number (same convention
Task 07/08's `VideoPerformance` fields already use).

## Two "video" pipelines -- a real architecture gap, resolved with the user

This app has two disconnected notions of "a video": Library videos
(`Video`, enriched with Story/Hook/Caption/Quality Score via
`ai_generation_history.video_id`) and Video Factory's produced videos
(`VideoComposeJob`, optionally with AI-generated images via `FactoryRun`).
No link exists between `StoryJob` and `VideoComposeJob` in this codebase
-- confirmed with the user before building this (see conversation):
"Videos Generated" / "Average Cost / Video" use `VideoComposeJob`'s own
completed count (matching the existing Production Dashboard's
definition, Task 43). Cost per video only ever includes AI Image
Generation cost (`FactoryRun.visual_generation_cost_usd`, joined via
`render_job_id`) -- Story/Hook/Caption/Scoring costs are counted in full
in the overall `AI Cost`/`Cost by Provider`/`Cost by Model` totals but
deliberately **not** folded into `Cost / Video`, since there's no real
link to misattribute them through. The UI's own hint text says this
explicitly.

A second, disclosed (not fixed) gap: Beat/Content-Brief/Script
generation (`content_generate.py`/`beat_generate.py`) call the shared
LLM client but never call `history.record()`, so Video Factory's own
text-generation cost isn't tracked at all yet -- out of this task's
explicit scope (Story/Hook/Caption/Scoring/Image/TTS), not fixed here.
Caption generation itself has no code today (deleted in Task 63, never
restored -- only Story/Hook were, in Task 69); `"caption"` stays a
supported `kind` in the cost abstraction for old rows and forward
compatibility, without needing new generator code.

## Layers

- `app/modules/ai/cost_service.py` -- core layer, stays inside the `ai`
  module boundary (`AIGenerationHistory` + `StoryJob`/`StoryVersion` are
  sub-packages of the same module). Turns raw history rows into priced
  `AICallCost` entries, groups by provider/model/month, and resolves
  `quality_score` rows (whose `job_id` points at `story_version.id`) back
  to their parent `StoryJob` for cost-per-story.
- `app/api/v1/endpoints/ai_costs.py` -- composition root, the one place
  allowed to import `cost_service` together with `content_batch`
  (cost per batch) and `factory`/`video_composer` (image cost, videos
  generated). `GET /ai-costs/summary|calls|stories|batches|videos`, all
  read-only.

## UI

New `/ai-costs` page (Sidebar: "AI Cost Tracking"): 4 KPI cards (AI Cost,
Videos Generated, Average Cost / Video, Cost / 1,000 Videos), `BarRanking`
sections for Cost by Provider/Model/Month, and simple tables for Cost per
Story/Batch. A warning banner appears whenever unconfirmed pricing
contributed to a nonzero total.

## Verification

Real end-to-end math check against an isolated backend+DB+frontend
(ports 8011/5190, never touching the user's own 8000/5173): 1 StoryJob
(story + quality_score calls, anthropic), 1 hook call (openai), 1
ContentBatch wrapping that story, 1 completed `VideoComposeJob` with a
linked `FactoryRun` (6 AI images, $0.036). Hand-computed every number --
`0.0105+0.0021+0.0085=0.0211` text cost, `+0.036` image `=0.0571` total,
`by_provider["openai"]=0.0085+0.036=0.0445`, `average_cost_per_video=
0.036/1`, `cost_per_1000_videos=36.00` -- all matched the API responses
exactly, digit for digit. Real Playwright screenshot confirms the UI
renders the same numbers with zero console errors.

`python -c "import app.main"` and `npx tsc -b --noEmit` both clean.
