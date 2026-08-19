# 59 — "Generate Full by AI": per-beat OpenAI image generation

**Commit:** `TBD`

A new, distinct "Generate Full by AI" button (New Video modal): paste a
full story, and the whole pipeline (Beats -> Images -> Voice -> Motion ->
Audio -> Captions -> Render) runs automatically, except each beat's image
comes from a fresh OpenAI-generated image instead of a match from the
local Asset Library. Opt-in per project (`visual_generation.mode` on
`ProjectConfig`, defaults to `"library"`) -- every existing project and
the classic "Create & Produce" flow is completely unaffected.

A deliberate, user-confirmed departure from this app's usual "$0/video,
local-only" design: the user has their own working OpenAI credit and
wants this specifically, after independently verifying OpenAI's own
pricing. Model/price: `gpt-image-1-mini`, quality `low`, size `1024x1536`
(portrait) ≈ $0.006/image, ~$0.04-0.05 for a typical 6-8 beat video.

## How it fits the pipeline

- `app/modules/ai/image_client.py` -- thin OpenAI Images API wrapper
  (base64-decode, atomic write). Always uses `settings.openai_api_key`
  directly; independent of Task 55's text-provider toggle (Claude has no
  image API).
- `app/api/v1/endpoints/imagegen_generate.py` -- composition root:
  generates one image per beat with `asset_id is None`, registers it as a
  real Asset (`source="ai_image_generator"`), assigns `beat.asset_id`. A
  per-beat failure (content-policy rejection, transient error) is a soft
  skip -- never fails the whole stage over one beat, same precedent as
  BGM-missing/Motion-cache-miss.
- Wired into the existing (previously inert, pass-through) `PREPARING_VISUALS`
  stage slot in `factory_pipeline.py` -- for `mode == "ai_generated"` it
  now does real, checkpointed work; `mode == "library"` (default) keeps
  the exact prior pass-through/SKIPPED behavior. No new `FACTORY_STAGES`
  entry was needed.
- Downstream stages (Motion, Quality Gate, Render) needed zero changes --
  none of them special-case `Asset.source`, and `ASSIGNING_ASSETS` already
  skips any beat with `asset_id` already set.
- `FactoryRun.visual_generation_image_count`/`visual_generation_cost_usd`
  (new columns, added to `app/db/migrate.py`'s `_NEW_COLUMNS`) record the
  real per-run count/cost; both stay `NULL` for `"library"` mode runs.

## Frontend

`NewVideoModal.tsx` gained a "Generate Full by AI" button (requires the
Script field, shows a static cost estimate, disabled without a configured
OpenAI key) that creates the project with `visual_generation_mode:
"ai_generated"` and always auto-produces. `ReadyToPostCard` shows the
real per-run "AI images: N ($X.XX)" once known.

## Verification

Backend: `tests/modules/ai/test_image_client.py` (mocked-boundary decode/
error tests), `tests/api/test_imagegen_stage.py` (idempotency, per-beat
soft-fail, retry-never-rebills, pipeline mode dispatch/checkpoint/error
code) -- full suite green. Frontend: `tsc -b --noEmit` and `vite build`
both clean.
