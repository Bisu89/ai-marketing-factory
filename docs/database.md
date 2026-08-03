# Database

SQLite, no migration framework yet -- `Base.metadata.create_all()` runs at
startup (additive only; it won't drop/alter existing columns). `app/db/seed.py`
idempotently seeds `platform`, `category`, and `emotion` on every startup.

## Entity overview

```
platform (youtube/tiktok/facebook/instagram, seeded)
  └─ channel (platform_id FK, name)  UNIQUE(platform_id, name)
       └─ video (channel_id FK, platform_id FK, external_id, title, ...)
            UNIQUE(platform_id, external_id)   <- the dedup key
       └─ playlist (channel_id FK, platform string, external_id)
            └─ playlist_video (playlist_id, video_id)  join table

video
  ├─ category (category_id FK, nullable)        many-to-one -- labeled "Topic" in the UI
  ├─ emotion (emotion_id FK, nullable)           many-to-one
  ├─ favorite (video_id FK == PK)                zero-or-one ("is favorited")
  ├─ tag  via video_tag (video_id, tag_id)        many-to-many
  ├─ download_task (video_id FK)                  one-to-many (lifecycle/queue)
  ├─ download_history (video_id FK, task_id FK)   one-to-many (append-only log)
  └─ story_job (video_id FK)                      one-to-many
       └─ story_version (story_job_id FK)         one-to-many (2 per job)
```

## Why `video.platform_id` duplicates `channel.platform_id`

Strictly normalized, platform would only live on `channel` and be reached via
`video.channel_id → channel.platform_id`. It's kept directly on `video` too
so the dedup `UNIQUE(platform_id, external_id)` constraint (and platform
filters) don't depend on the channel row having been resolved consistently
across calls -- a deliberate, documented exception, not an oversight.

## Tables

### `platform`
| column | type | notes |
|---|---|---|
| id | PK | |
| name | unique | youtube / tiktok / facebook / instagram |

### `channel`
| column | type | notes |
|---|---|---|
| id | PK | |
| platform_id | FK → platform | |
| name | | UNIQUE with platform_id |
| external_id | nullable | reserved, not populated yet |
| url | nullable | |

### `video` — the canonical, deduplicated video record
| column | type | notes |
|---|---|---|
| id | PK | |
| platform_id | FK → platform | see note above |
| external_id | | the platform's own video id |
| channel_id | FK → channel | |
| title, original_url | | |
| thumbnail_url | nullable | source URL (e.g. YouTube's CDN thumbnail) |
| thumbnail_path, video_path | nullable | **server filesystem paths**, set once downloaded/organized. Not directly browser-loadable -- see `thumbnail_media_url`/`video_media_url` in the API. |
| views, likes, duration_sec, upload_date | nullable | source metadata |
| status | default `downloaded` | content workflow: `downloaded / ready / published / archived`, plus `deleted` as a soft-delete marker outside the visible workflow |
| category_id | FK → category, nullable | labeled "Topic" in the UI (see [12-content-workflow.md](features/12-content-workflow.md)) |
| emotion_id | FK → emotion, nullable | |
| notes | nullable | free text (markdown, per UI) |
| resolution | nullable | not auto-populated yet (would need ffprobe) |
| filesize_bytes | nullable | populated from the real file at organize time |
| file_hash | nullable | reserved for future dedup-by-content |
| is_downloaded, downloaded_at | | set by the download engine on success |

`UNIQUE(platform_id, external_id)` is the hard dedup constraint. The API
additionally checks it at the service layer before enqueuing a download so a
duplicate returns a clean `409` instead of a raw DB error.

### `category` — seeded, fixed set for now
Couple, Family, Military, Proposal, Transformation, Comedy, Other. Labeled
"Topic" in the UI (see [12-content-workflow.md](features/12-content-workflow.md)
for why the table wasn't renamed to match).

### `emotion` — seeded, fixed set for now
Vui, Cảm động, Hài hước, Buồn, Kịch tính, Trung tính. Same read-only-lookup
shape as `category` (GET-only, seeded once, no create/edit endpoint).

### `tag` / `video_tag`
Free-form, user-created tags, many-to-many with video. Created on first use
(`TagService.create` / `VideoLibraryService.add_tags` get-or-create by name).
Merging (`POST /tags/merge`) reassigns `video_tag` rows from source to target
tag and de-dupes if a video already has both.

### `favorite`
`video_id` is both the PK and the FK -- presence of a row means "favorited".
Single-user app; if multi-user is ever added, this needs a `user_id` column
and a composite PK.

### `playlist` / `playlist_video`
Optional grouping; a video can belong to multiple playlists. Not surfaced in
any UI yet -- schema-ready for when playlist-level browsing/download is built.

### `download_task` — the download queue/lifecycle
| column | notes |
|---|---|
| video_id | FK → video |
| url | direct URL passed to the Downloader |
| destination_path | staging path during download (not the final library path) |
| status | `queued / downloading / paused / completed / failed / cancelled` |
| attempts, error_message | |
| downloaded_bytes, total_bytes, progress_pct, speed_bps, eta_seconds | live progress |

### `download_history` — append-only outcome log
One row per terminal transition (`completed` / `failed` / `cancelled`) with
`video_id`, `task_id`, `error_message`, `occurred_at`. Kept separate from
`download_task` so history survives even if task rows are ever pruned.

### `story_job` / `story_version` — AI Story generations (`app/modules/story/`)
One `story_job` row per generation request (`video_id` FK, `style`, `status`
`completed`/`failed`, `error_message`), with 2 `story_version` rows per
completed job (`title`, `script_text`, `is_selected`). Written synchronously
inside the same request that calls Claude -- there is no background
queue/worker for this module, unlike Scene Cutter/Video Composer, because an
LLM text call is fast enough to not need one (see
[13-ai-story.md](features/13-ai-story.md)).
