# 08 — Library backend API (Sprint V8, Milestone 1 + 2)

**Commits:** `365a019` (Milestone 1: DB), `fb75990` (Milestone 2: APIs, part
of "Sprint V8 Milestone 2+3")

## What it does

Turns the video catalog from "rows written by the download flow" into a
browsable, editable library with a proper REST API: search, filter, sort,
pagination, status, category, tags (create/rename/delete/merge), favorites,
soft/hard delete, and manually importing an existing local file.

## Architecture

Repository (`app/services/library/repository.py`) → Service
(`app/services/library/service.py`) → API
(`app/api/v1/endpoints/{videos,categories,tags}.py`). Endpoints are thin:
parse the request schema, call one service method, map the result. All
query-building lives in the repository; all business rules (status
validation, tag get-or-create, dedup-aware import) live in the service.

Custom exceptions (`app/core/exceptions.py`: `NotFoundError`,
`ValidationError`, `FileOperationError`) are raised by services and mapped
to friendly JSON responses by exception handlers registered in `main.py` --
endpoints never need their own try/except for these.

## Endpoints

```
GET    /videos?search=&platform=&status=&category_id=&tag=&favorite=
              &duration=&resolution=&sort=&page=&page_size=
POST   /videos                       (manual import of an existing local file)
GET    /videos/{id}
PUT    /videos/{id}                  (status / category_id / notes)
DELETE /videos/{id}?hard=false       (soft: status=deleted; hard: delete file+row)
POST   /videos/{id}/favorite | DELETE
POST   /videos/{id}/tags | DELETE /videos/{id}/tags/{tag_id}
POST   /videos/{id}/open-folder      (video-scoped; see note in 07)

GET    /categories
GET/POST/PUT/DELETE /tags, POST /tags/merge
```

`search`/`filter`/`sort`/pagination are deliberately one endpoint
(`GET /videos?...`) rather than the originally-sketched separate
`/videos/search` and `/videos/filter` -- one collection endpoint with query
params, per REST convention, avoids duplicating pagination/sort logic three
ways.

## Notable design points

- **Manual import** (`POST /videos`) copies (not moves) the source file --
  it's the user's pre-existing file elsewhere on disk, not a temporary
  download artifact. Auto-generates an `external_id` if none given.
- **Tag merge** reassigns `video_tag` rows from source→target tag and
  de-dupes if a video already has both (verified: no duplicate link, no
  orphaned tag).
- **Hard delete** removes the video's entire `library/.../<video_id>/`
  folder plus its `DownloadTask`/`DownloadHistory` rows, not just the
  `Video` row.

## Bug caught during verification

Hard-deleting a video crashed (500) the first time it was tried: `Video`'s
`favorite`/`tags` relationships were joined-loaded and stayed in the
SQLAlchemy session's identity map after a bulk `DELETE` on the `favorite`
table; when `session.delete(video)` ran next, SQLAlchemy tried to
null-out the (already-gone) `Favorite.video_id`, which is illegal because
that column is both PK and FK. Fixed with `session.expire(video)`
immediately before the delete. Caught by actually calling the endpoint, not
by reading the code.
