# 131. AI Storytelling Studio — Phase 1 (Story data model + Alembic)

The first schema increment of the AI Storytelling Studio plan. New
`app/modules/story/` planning layer (10 tables) + the first Alembic
migration. **No pipeline yet** — Phase 2 builds the planning pipeline on
top; the `/story-*` routes are pure CRUD.

## What it does and why

### `app/modules/story/` — the planning hierarchy
`StoryChannel → Series → Episode → Story → StoryChapter → StoryScene`,
plus `StoryCharacter` / `StoryLocation` bibles and a resumable
`StoryRun` / `StoryCheckpoint` (a 1:1 mirror of
`app.modules.factory.FactoryRun` / `FactoryCheckpoint`, so Phase 2's
pipeline gets crash recovery + retry for free).

- **Module-self-contained.** Real FKs *within* the module; every reference
  *out* (`Asset.id`, `Project.id`, `ContentIdea.id`, `YouTubeChannel.id`,
  `Series.id`) is a bare int, no FK/import — the same convention
  `FactoryRun.project_id` / `Project.series_id` already use. `Episode.series_id`
  is a bare int; an orphan is harmless, not an error worth a cross-module lookup.
- `StoryScene` ≈ `Beat` extended with the Scene Director score columns
  (`importance_score` … `composite_score`, all NULL until Phase 4 fills
  them), `dialogue_json`, `visual_mode` / `visual_mode_source`
  ("USER" freezes the mode so a re-run never overrides it).
- `Story.project_config_json` is an opaque `ProjectConfig` blob in Phase 1
  — the Phase 2 pipeline (a composition root, allowed to import `beat`)
  validates it. Status / mode / scope strings are validated in `schemas.py`
  (Pydantic), never a DB CHECK — same as every other status field here.

### `series/` extended
5 additive columns on the existing `series` table (`channel_id`,
`narrative_identity`, `visual_identity_json`, `voice_override_json`,
`metadata_conventions_json`) + `PUT /series/{id}/studio`. The classic
`series_project.py` flow and `character_description` are untouched.

### `story_channel`, not `channel`
`channel` is already the core "platform channel a downloaded video belongs
to". The class is `StoryChannel`, table `story_channel`.

### Alembic (feature Q6)
`Base.metadata.create_all()` stays the authority for what a **fresh**
schema looks like (idempotent — it only ever CREATEs missing tables).
Alembic is the **catch-up + rollback** layer for a database created by an
**older** app version. `app/db/schema.py::sync_schema` (replaces the raw
`create_all` + `run_additive_column_migrations` in `main.py`'s lifespan):

1. `create_all()` — brand-new tables
2. `run_additive_column_migrations()` — the frozen legacy column list
   (the 5 `series` columns were added here too, since an unversioned DB is
   stamped, never migrated)
3. no `alembic_version` table → `alembic stamp head` (create_all just
   produced the current schema); else → `alembic upgrade head`

Consequence for migration authors: **ALTER-only** where a migration
touches a table `create_all` owns. `0001`'s `create_table` for the story
tables exists only for `alembic downgrade base && upgrade head` cycling —
in normal operation it never runs. Programmatic `Config` (no `alembic.ini`
needed at runtime); `render_as_batch=True` for SQLite ALTER support.
`alembic/` is bundled as PyInstaller data.

## Key files

- **New:** `app/modules/story/{__init__,models,schemas,service,router}.py`,
  `app/db/all_models.py`, `app/db/schema.py`, `alembic/` (`env.py`,
  `versions/0001_storytelling_studio_phase1.py`), `alembic.ini`
- **Modified:** `app/modules/series/{models,schemas,service,router}.py`
  (+ studio columns/endpoint), `app/db/migrate.py` (+ 5 series columns +
  index), `app/main.py` (`sync_schema`, `reconcile_story_runs_on_startup`),
  `app/api/v1/router.py` (mount `story_planning_router`),
  `AIContentLibrary.spec` (bundle `alembic/`), `requirements.txt`
  (`alembic==1.14.0`)
- **Tests:** `tests/modules/story/{test_service,test_schema_bootstrap}.py`
  (CRUD; fresh-DB / pre-131-DB catch-up / downgrade↔upgrade round-trip),
  `tests/modules/series/test_service.py` (+ studio patch)

## Real bugs caught during verification

- `story.Channel` collided with the core `channel` table on
  `__tablename__`, and — after that — on the class name `Channel` in the
  shared declarative registry (breaking `Video.channel` relationship
  resolution). Renamed class + table to `StoryChannel` / `story_channel`.
- First cut had `story/` importing `app.modules.series.models` and
  `app.modules.beat.schemas` — module-isolation violations. Moved the
  Series-studio CRUD into the `series/` module and kept
  `Story.project_config_json` opaque (Phase 2's composition root validates it).
- `sync_schema` originally trusted the caller to have imported the model
  modules — an incomplete `Base.metadata` meant `create_all` silently
  skipped tables. Fixed by having `schema.py` import `app.db.all_models`.
- On an existing DB (has `series`, no new columns, no `alembic_version`),
  `stamp head` recorded `0001` without running it, so the 5 series columns
  never got added. Fixed by also listing them in `migrate.py`.

## Landed in

`e8e4867` — 862 `tests/modules/` pass + factory/batch regression; real
`uvicorn app.main:app` boot against a fresh DB with full `/story-*` CRUD
over HTTP verified.
