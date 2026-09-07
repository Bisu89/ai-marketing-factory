# 129. Extract the Factory stage functions into `factory_stages.py`

Pure refactor, no behaviour change. Prep step for a future long-form AI
story pipeline (`story_pipeline.py`) that needs to reuse the exact same
per-stage worker bodies — voice, motion, audio, captions, quality/render
handoff, packaging, final QA — without depending on
`factory_pipeline.py`'s single-project orchestration, batch engine, and
HTTP routes.

**What changed**
- New `app/api/v1/endpoints/factory_stages.py` holds the 20 symbols moved
  verbatim out of `factory_pipeline.py`: `_stage_generate_content`,
  `_stage_generate_beats`, `_auto_assign_visual`, `_stage_assign_assets`,
  `_count_beats_needing_policy_review`, `_stage_generate_images`,
  `_stage_generate_motion`, `_stage_generate_voice`,
  `_stage_generate_audio`, `_stage_generate_captions`,
  `_run_quality_and_proceed`, `_stage_render`, `_stage_package`,
  `_stage_final_qa`, `_settle_after_final_qa`, `_run_final_qa_and_settle`,
  plus the shared `FactoryStageError`, `_mark_failed`,
  `_bail_if_cancelled`, `_utcnow` primitives.
- `factory_pipeline.py` (2018 → ~1360 lines) keeps every orchestration
  entry point (`_execute_pipeline_sync`, `create_and_start_run`,
  `continue_run`, `retry_run`, `cancel_run`, the cancel-event registry),
  the whole batch engine, the `render.job.*` event handlers,
  `reconcile_*_on_startup`, and every route — and **re-imports** the 20
  names from `factory_stages` so `from …factory_pipeline import <name>`
  resolves unchanged everywhere (the re-exported objects are the *same*
  objects, so `except FactoryStageError` / `isinstance` still work).
- No new module imports; same composition-root rules as
  `factory_pipeline.py` / `batch_render.py`. `factory_stages.py` has no
  `APIRouter` — it is called, never routed. Not added to `api/v1/router.py`.

**Tests**: the stage-test suite patched internal dependencies by their
location in `factory_pipeline` (`patch("…factory_pipeline.generate_beat_plan")`,
`…generate_content_brief`, `…generate_script`, `…generate_project_images`,
`…generate_project_captions`, `…generate_project_package`,
`…run_final_qa`, and `…factory_pipeline.SessionLocal`). Those 30-odd patch
targets were retargeted to `factory_stages` (the real new home), and
`_FactoryTestCase.setUp` now patches `factory_stages.SessionLocal`
alongside the existing `factory_pipeline.SessionLocal`. `_execute_pipeline_sync`
/ `get_settings` patches were left as-is (still live in `factory_pipeline`).

**Landed in**: `TBD`

**Key files**: `backend/app/api/v1/endpoints/factory_stages.py` (new),
`backend/app/api/v1/endpoints/factory_pipeline.py`,
`backend/tests/api/test_{factory_pipeline,factory_reliability,batch_factory_engine,content_stage,imagegen_stage,voice_stage,motion_stage,audio_stage,caption_stage,package_stage,final_qa_stage}.py`.
