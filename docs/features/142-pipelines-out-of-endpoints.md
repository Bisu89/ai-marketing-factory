# 142. Refactor (P3): move composition roots to `app/pipelines/`

Pure structural move, no behaviour change. The review's finding #4 was
"endpoint files doing business logic" — the eight cross-module
orchestrators lived under `app/api/v1/endpoints/` (they carry an
`APIRouter`) but their real job is stage sequencing + `FactoryRun`/
`StoryRun` state, not HTTP.

**Landed in:** _branch `refactor/p3-pipelines-out-of-endpoints`_

**Moved** (filenames unchanged, so the only code change is the import
path `app.api.v1.endpoints.X` → `app.pipelines.X`):

    factory_pipeline.py  factory_stages.py
    story_pipeline.py     story_stages.py    story_compile.py
    news_pipeline.py      batch_render.py    content_batch_generate.py

~5300 lines of orchestration out of the HTTP layer. `app/api/v1/router.py`
imports the six router-carrying ones from `app.pipelines`; `app/main.py`'s
reconcile/event-handler imports follow. ~20 test files updated (mechanical
`from app.pipelines import ...`).

**Deliberately NOT done (follow-up P3b):** the reusable per-stage helpers
these files still import from `app/api/v1/endpoints/*_generate.py`
(`generate_beat_plan`, `run_quality_check`, `render_composition`,
`generate_project_*`) stay put. A pipeline importing from `endpoints/` is
still backwards layering — pulling each helper into its owning
`app.modules.<x>` is the next pass. This move alone already makes the
orchestration findable and gets it out of the router layer.

**P1 (unify `FactoryRun`/`StoryRun`) was assessed and dropped:** the two
models have genuinely diverged for product reasons (StoryRun has `scope`,
a real FK to `story`, per-language targeting, compiled-project-id
tracking; FactoryRun has `render_job_id`, quality/QA scores, visual-gen
cost). Merging them would be a forced fat-nullable model or inheritance
complexity, and it's the one change needing an Alembic migration on live
user data. Not worth the risk/reward.

**Verified:** the factory/story/batch/news pipeline + all per-stage
(voice/motion/audio/caption/package/QA/imagegen) + final-composer test
suites.
