# 157 — Remove unused features

**Commit:** `9af3123`

At the user's request, eleven features the user doesn't use were removed
outright (code, routes, UI, tests), not just hidden from the sidebar:

| Feature | Backend removed | Frontend removed |
|---|---|---|
| Viral Source Radar | `modules/discovery` | `RadarPage` |
| Tin tức (News) | `modules/news`, `pipelines/news_pipeline.py`, the RSS poll thread in `main.py`, `feedparser` | `NewsPage` |
| Content Batches | `modules/content_batch`, `pipelines/content_batch_generate.py` | `ContentBatchesPage`, `ContentBatchDetailPage` |
| Winner Detection | `endpoints/winner_detection.py`, `endpoints/performance_intelligence.py`, `services/insights/{winner_detection,performance,recommendation}_service.py` | `WinnerDetectionPage` |
| Competitor Analyzer | `modules/competitor_intelligence`, `endpoints/competitor_analysis.py` | `CompetitorIntelligencePage` |
| Affiliate Engine | `modules/affiliate` (incl. the `/r/{code}` redirect), `endpoints/affiliate_{recommend,performance}.py` | `AffiliatePage` |
| Scene Cutter | `modules/scene_cutter`, `scenedetect` | `SceneCutterPage` |
| Publishing (YouTube) | `modules/publishing`, `endpoints/publish_video.py` | `PublishingPage`, "Đăng lên YouTube" on the Videos page |
| Batches | `modules/batch`, `pipelines/batch_render.py`, the Factory Batch Engine in `factory_pipeline.py` | `BatchPage`, `BatchDetailPage`, "New Batch" on the Dashboard |
| Content Studio | `modules/content_strategy`, `endpoints/content_{idea_generation,recommendations}.py` | `ContentStudioPage`, `features/contentStudio` |
| Series | `modules/series`, `endpoints/series_project.py` | `SeriesPage`, `SeriesDetailPage`, the series step in `NewVideoModal` |

Their settings went with them: TikTok client key/secret/redirect URI,
YouTube Data API key + Reddit credentials (Radar), Google OAuth client +
YouTube redirect URI (Publishing), and the RSS poll interval. AI Cost
Tracking was explicitly kept; it only lost its "Cost per Batch" table.

## What had to change in the features that stay

- **Factory pipeline.** The only thing it used from `batch_render.py` was
  the BeatPlan -> CompositionPlan translation, which moved unchanged to
  `app/pipelines/composition_plan.py`. Every `_sync_batch_after_run_settled`
  call and the whole Batch Engine section (pause/resume/cancel/retry, the
  bounded `ThreadPoolExecutor`, `reconcile_batches_on_startup`) are gone.
- **Dashboard** (`endpoints/dashboard.py`) used to aggregate only over
  BatchItems. It now aggregates over every Project, judged by its latest
  FactoryRun: the Quality Gate runs for projects never rendered with no run
  yet, or whose run sits in NEEDS_REVIEW; "Needs attention" lists FAILED
  runs plus Quality Gate BLOCKED/NEEDS_REVIEW; "Pipeline" counts latest-run
  statuses. The "current batch" card is gone.
- **Videos page / `GET /produced-videos`** lost the batch and series
  filters; a render is linked to its project via `Project.render_job_id`.
- **Render-cache cleanup** (`assets_cleanup.py`) finds a project's render
  jobs through `Project.render_job_id` only.

## Design decisions

- **No database data is dropped.** Tables of removed features stay in an
  existing database, unused. Model columns that pointed at removed
  features (`PublishLog.affiliate_link_id`, `Project.series_id`/
  `episode_number`, `StoryJob.content_idea_id`) stay on their models,
  unread and unwritten -- the same approach as
  [63-remove-ai-content-and-insights.md](63-remove-ai-content-and-insights.md).
  Storytelling Studio's own `Episode.series_id`/`Story.content_idea_id`
  are untouched (bare ints, part of that feature's schema).
- **Alembic migrations 0001/0002 were made conditional**, not deleted:
  0001 alters the `series` table and 0002's downgrade drops the discovery
  tables, neither of which exists in a database created after this change.
  Both now check `has_table` first, so old databases still upgrade exactly
  as before and `downgrade base && upgrade head` still cycles on new ones.
- **Old `.env` keys are harmless.** `Settings` has `extra="ignore"`, so an
  existing `.env` still holding `APP_TIKTOK_*`, `APP_NEWS_POLL_*` etc.
  loads fine.
- The publish log's manually entered `affiliate_product`/clicks/sales/
  revenue fields are older than the Affiliate Engine and belong to the
  Library's publish log, so they were kept.

## Verification

- `python -c "import app.main"` succeeds; `npx tsc -b` and `vite build` are
  clean; every test module imports.
- Tests for removed features were deleted. `test_dashboard.py` and
  `test_produced_videos.py` were rewritten on a Project/FactoryRun harness
  (the old one was the batch harness). The schema-bootstrap tests no
  longer expect a `series` table.
