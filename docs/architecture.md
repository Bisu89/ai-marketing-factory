# Architecture

## Stack

- **Backend**: FastAPI (Python), SQLAlchemy 2.0 ORM, SQLite, `uvicorn`
- **Frontend**: React 19 + TypeScript, Vite, React Router, TanStack Query
- **Download**: `yt-dlp` for real platform extraction/download; a generic HTTP-range `Downloader` interface backs it

## Backend layers

```
app/api/v1/endpoints/*.py   <- HTTP layer: parse request, call service, map response.
                                No SQL, no business rules here.
app/services/<area>/service.py   <- Business rules (validation, status transitions,
                                     tag get-or-create, dedup checks, ...)
app/services/<area>/repository.py <- Query/persistence only, no business logic.
app/models/*.py              <- SQLAlchemy ORM models (the schema)
app/schemas/*.py              <- Pydantic request/response shapes
app/core/                     <- config, logging, events (EventBus), exceptions
app/db/                       <- engine/session wiring, seed data
```

This Repository → Service → API split is the standard for **new** library-facing
code (`app/services/library/*`). Older infrastructure (`app/services/download/*`)
predates the convention and talks to the DB directly inside the engine —
that's accepted technical debt, not something to "fix" opportunistically
inside unrelated feature work.

Dependency injection is plain FastAPI `Depends()` (see `app/api/deps.py`) —
no DI framework. Long-lived singletons (the download engine, the event bus)
live on `app.state`, created once in `main.py`'s `lifespan`.

## Folder structure

```
backend/
  app/
    api/v1/endpoints/   one file per resource (videos, downloads, tags, categories, detect, health)
    core/                config.py, logging.py, events.py, exceptions.py
    db/                   base.py (declarative Base), session.py, seed.py
    models/               one file per table
    schemas/              one file per resource, Pydantic I/O shapes
    services/
      download/           DownloadEngine + pluggable Downloader (HttpDownloader, YtdlpDownloader)
      library/             catalog.py (get-or-create Channel/Video), organizer.py (file layout),
                            repository.py + service.py (Video/Tag/Category business logic)
      detect/               yt-dlp-backed URL → platform/metadata detection
    modules/               README.md only for now -- convention for future
                            standalone feature modules (subtitles, captions,
                            voice, affiliate matching, analytics). See
                            features/06-extensibility-eventbus.md.
  data/                   SQLite file + downloaded/organized media (gitignored)

frontend/
  src/
    api/                  thin fetch wrappers per resource (client.ts has the
                           shared apiGet/Post/Put/Delete + mediaUrl helpers)
    components/            shared UI atoms (Sidebar, PageHeader, PlatformBadge, ...)
    features/library/       Library-page-specific components/hooks/types
                            (kept separate from components/ since they're not
                            reused outside the Library page)
    layouts/                AppShell (sidebar + routed content)
    pages/                  one component per route
    types/                  shared TS types
```

## Data flow: URL to organized library entry

1. Frontend `DownloadPage` calls `POST /api/v1/detect` with a pasted URL.
2. `services/detect/ytdlp_detector.py` runs yt-dlp in metadata-only mode
   (`skip_download: true`) and returns platform + video/collection metadata.
3. User confirms; frontend calls `POST /api/v1/downloads` with that metadata.
   The API layer (`catalog.find_video`) checks for an existing
   `(platform, external_id)` — already-downloaded videos are rejected with
   409, in-flight duplicates reuse the existing task.
4. `DownloadEngine` runs the download on a background worker thread
   (`YtdlpDownloader`), reporting progress/speed/ETA back onto the
   `DownloadTask` row without blocking the API.
5. On success, `services/library/organizer.py` moves the file into
   `library/<platform>/<channel_name>/<video_id>/video.mp4` (+ thumbnail.jpg +
   metadata.json) and the `Video` row is marked downloaded.
6. `DownloadEngine` publishes a `video.downloaded` event on the `EventBus` --
   any future module can react without the engine knowing it exists.
7. The Library page (`/videos` API + React Query) shows the video: searchable,
   filterable, taggable, favoritable.

See [database.md](database.md) for the full schema and
[features/](README.md#features-chronological) for how each piece was built.
