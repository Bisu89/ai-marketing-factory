# 20 — Asset Module (local asset library)

**Commit:** _(fill in after commit)_

## What it does

A self-contained local asset library for the future Video Factory: register
an image/video/audio file (by filesystem path), tag it, and later find it
again via deterministic keyword search. `POST /assets`, `GET /assets?q=...&asset_type=...`,
`GET /assets/{id}`, `DELETE /assets/{id}`.

This is intentionally scoped to registration + search + lookup only — no
rendering, no motion, no beat assignment. It exists so a future Beat/Motion
step (see [video_factory_architecture.md](video_factory_architecture.md))
has real assets to search and pick from.

## Key files

`backend/app/modules/asset/{models,schemas,service,router}.py`,
`backend/tests/modules/asset/{test_schemas,test_service}.py`. Wired in
`backend/app/api/v1/router.py` only — no `app/main.py` change, since this
module has no background worker (every operation is a fast local DB
read/write, same shape as `app/modules/ai/story`'s synchronous service).

## Non-obvious design decisions

- **Tags are a JSON column on `asset`, not a join table against the core
  `tag`/`video_tag` dimension.** Reusing `app/models/tag.py` would couple
  this module to Library-video-tagging behavior (merge, get-or-create-by-
  name) it doesn't need, and — more importantly — a real FK to a core table
  the module doesn't otherwise touch adds a dependency this module doesn't
  need for anything it actually does. A plain `list[str]` column keeps the
  table's only dependency being `app.db.base.Base`.
- **`source`/`source_ref` are plain strings, not a foreign key to `video.id`**,
  even though a module→core FK (like `SceneCutJob.video_id`) is normally
  fine per `app/modules/README.md`. Kept as free text here specifically so
  this module has *zero* schema dependency on any other table — provable in
  the test suite, which creates only the `asset` table
  (`Base.metadata.create_all(bind=engine, tables=[Asset.__table__])`) and
  never touches the rest of `Base.metadata`.
- **No ffprobe/ffmpeg call anywhere in this module.** `scene_cutter` and
  `video_composer` each already duplicate their own `subprocess`-based
  ffprobe helper; adding a third copy here to auto-detect width/height/
  duration at registration wasn't justified for this slice — `width`,
  `height`, and `duration_sec` are accepted as caller-supplied, optional
  fields instead. This keeps the module's only real dependencies as
  SQLAlchemy + the standard library, satisfies "no external service is
  required," and keeps the test suite fast/deterministic (no ffmpeg binary
  needed to run `python -m unittest`). A future ingestion path (e.g. one
  that copies a Scene Cutter output into the asset library) can probe with
  ffprobe itself and pass the result in.
- **`is_ready` is a computed property (file still exists on disk right
  now), never a stored column** — the same reasoning as `Video.is_favorite`/
  `channel_name` elsewhere in this app: derived state can't go stale if it's
  never persisted, and a registered asset's file can be moved or deleted
  outside this app at any time.
- **Search is deterministic keyword scoring, not embeddings/vector search**,
  per the task constraint: exact tag match (+3) > partial tag substring
  match (+2) > filename/source substring match (+1 each), summed per query
  term; zero-score assets are excluded rather than ranked last. An empty
  query returns everything sorted by `created_at` descending instead of an
  empty result set.
- **Path normalization dedups registrations of the same physical file.**
  `path` is resolved to an absolute path (`Path.resolve()`) before it's
  compared or stored, and the column is `UNIQUE` — registering `"./clip.mp4"`
  and `"C:/repo/clip.mp4"` (the same file) a second time raises a
  `ValidationError` instead of silently creating a duplicate row.

## Verification

`python -m unittest discover -s tests` — 42 tests total (26 new for this
module: Pydantic-level metadata validation, registration + computed fields,
duplicate-path/missing-file/directory-path rejection, missing-asset lookup/
delete, search ranking including case-insensitivity and type filtering, and
filesystem path normalization). All pass. Also confirmed `app.main.create_app()`
instantiates cleanly with the new router mounted (`/api/v1/assets*` routes
present) without touching the real dev database.
