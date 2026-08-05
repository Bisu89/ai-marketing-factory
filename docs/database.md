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
  ├─ story_job (video_id FK)                      one-to-many
  │    └─ story_version (story_job_id FK)         one-to-many (2 per job)
  ├─ hook_job (video_id FK)                       one-to-many
  │    └─ hook_version (hook_job_id FK)           one-to-many (5-10 per job)
  ├─ caption_job (video_id FK)                    one-to-many
  │    └─ caption_version (caption_job_id FK)     one-to-many (2 per job)
  └─ publish_log (video_id FK)                    one-to-many
       linked by post_id/page_id, not a FK, to ->
       insight_upload (CSV upload)
         └─ insight_post_snapshot (upload_id FK)  one-to-many (1 per post per upload)

ai_generation_history                              one row per Claude call
  job_id (bare int, not FK -- points at story_job/hook_job/caption_job by `kind`)
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

### `story_job` / `story_version` — AI Story generations (`app/modules/ai/story/`)
One `story_job` row per generation request (`video_id` FK, `style`, `status`
`completed`/`failed`, `error_message`), with 2 `story_version` rows per
completed job (`title`, `script_text`, `is_selected`). Written synchronously
inside the same request that calls Claude -- there is no background
queue/worker for this module, unlike Scene Cutter/Video Composer, because an
LLM text call is fast enough to not need one (see
[13-ai-story.md](features/13-ai-story.md)).

### `hook_job` / `hook_version` — Hook generations (`app/modules/ai/hook/`)
One `hook_job` row per generation request (`video_id` FK, `status`,
`error_message`), with 5-10 `hook_version` rows per completed job (`text`,
`is_favorite`). Regenerating creates a new `hook_job` rather than mutating
the previous one, so past batches stay visible (see
[16-ai-content-platform.md](features/16-ai-content-platform.md)).

### `caption_job` / `caption_version` — Caption generations (`app/modules/ai/caption/`)
One `caption_job` row per generation request, with 2 `caption_version` rows
per completed job, each carrying all five fields together
(`facebook_caption`, `instagram_caption`, `youtube_description`,
`pinned_comment`, `cta`, `is_selected`) since they're generated with shared
context in one Claude call (see
[16-ai-content-platform.md](features/16-ai-content-platform.md)).

### `ai_generation_history` — one row per Claude call (`app/modules/ai/history.py`)
Shared across Story/Hook/Caption: `kind` (story/hook/caption), `job_id`
(bare `Integer`, deliberately not an FK since it must point at three
different tables depending on `kind`), `video_id` FK, `provider`, `model`,
`prompt_system`, `prompt_user`, `response_raw`, `latency_ms`,
`input_tokens`/`output_tokens`, `created_at`. Written for both success and
failure calls.

### `insight_upload` / `insight_post_snapshot` — Meta Business Suite CSV imports
One `insight_upload` row per CSV file uploaded on the Insights page; one
`insight_post_snapshot` row per post *per upload* (`app/services/insights/`,
`csv_parser.py`). A real-world post gets a new snapshot row on every
re-upload (cumulative/lifetime totals as of that moment), so growth over
time is read by comparing snapshots across uploads, not by mutating one row.
Not FK'd to `video` -- see `publish_log` below.

### `publish_log` — links a Library video to real published-post performance
One row per "I published this video" event, created manually (see
[15-performance-intelligence.md](features/15-performance-intelligence.md)):
`video_id` FK, platform/page_name, `hook_type`/`story_style` (creative
metadata no analytics export carries), `ai_story_job_id` (a bare int
reference into `story_job`, deliberately not an FK/relationship -- core
must never import `app/modules/*`), affiliate_* fields, and `post_id`/
`page_id` -- filled in *after* the fact, linking this row to whichever
`insight_post_snapshot` rows share that `post_id`/`page_id` (stable across
every snapshot of the same real-world post, so one link covers all of
them). Real performance numbers (views/interactions) are never stored here
-- always resolved live from the latest matching snapshot.
