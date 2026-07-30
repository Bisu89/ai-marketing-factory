# 05 — Catalog normalization (Videos/Channels/Playlists/Tasks/History)

**Commit:** `365a019` "Normalize catalog schema, add EventBus, Sprint V8 Milestone 1 (Library DB)"
(this file also introduced Platform/Category/Tag/VideoTag/Favorite; see
[08-library-backend-api.md](08-library-backend-api.md) for the Sprint V8
milestone that built the API on top of it)

## What it does

Splits what used to be a single `DownloadJob` row (URL + inline video
metadata + task lifecycle all on one table) into a proper normalized schema:
`Channel`, `Video` (the deduplicated canonical record), `Playlist` +
`PlaylistVideo`, `DownloadTask` (renamed from `DownloadJob`, now just a
lifecycle row referencing `video_id`), and `DownloadHistory` (append-only
outcome log).

Full table reference: [database.md](../database.md).

## Why

- **Dedup**: "each video exists exactly once" needed a real unique constraint
  (`(platform_id, external_id)` on `Video`), which is impossible while
  metadata lives inline per-task (every re-download attempt would just be
  another unrelated row).
- **History**: a durable per-video log of past attempts, independent of
  whether the originating task row still exists.

## Enforcement

`POST /downloads` (in `app/api/v1/endpoints/downloads.py`) checks
`catalog.find_video()` before enqueuing:
- video exists and `is_downloaded` → `409 Conflict` with the existing record
- video exists with an active (queued/downloading/paused) task → reuse that
  task instead of creating a duplicate (`200`, not `201`)
- otherwise → create the `Video` row and enqueue normally

## Migration note

No Alembic yet -- this was a pre-production schema change with no real user
data at risk, so it was a straight model rewrite plus deleting the dev SQLite
file, not a migration script.
