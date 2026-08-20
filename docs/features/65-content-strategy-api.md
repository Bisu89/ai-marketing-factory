# 65. Content Strategy: Backend API (Pillar → Format → Idea)

**Commit:** `2896884`

REST API on top of Task 21's `app/modules/content_strategy/` models. Adds
`repository.py` + `service.py` (Router → Service → Repository, matching
`app/services/library/`'s own split -- the module convention from Task 21
doesn't use a repository.py, but this task explicitly asked for that
layering, so it's added here) + `router.py`, mounted in
`app/api/v1/router.py`.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/content-pillars` | no filters, no pagination (small seeded lookup, same shape as `/categories`/`/emotions`) |
| GET | `/content-formats?pillar_id=` | `pillar_id` filter is a plain filter, not a lookup -- an unknown id returns `[]`, not 404 (matches `/videos?category_id=`) |
| GET | `/content-ideas?pillar_id=&format_id=&status=&min_score=&max_score=&page=&page_size=` | paginated (`page`/`page_size`, default 50, max 200), same envelope as `/videos` (`items`/`total`/`page`/`page_size`) |
| POST | `/content-ideas` | validates `pillar_id`/`format_id` exist (404), that the format actually belongs to the given pillar (400), and `target_emotion_id` exists if given (404) |
| GET | `/content-ideas/{id}` | 404 if missing |
| PATCH | `/content-ideas/{id}` | partial update: title/premise/target_emotion_id/commercial_intent/score/status |
| DELETE | `/content-ideas/{id}` | hard delete, 204, matches `PublishLog`'s own simple delete (no soft-delete concept on this table) |

No `POST`/`PATCH`/`DELETE` for Pillar or Format -- not in this task's
required endpoint list, and Pillar already followed the existing
Category/Emotion "seeded, GET-only" shape. **`/content-formats` will keep
returning `[]` until something inserts rows** -- Task 21 deliberately
didn't seed Formats (no pillar mapping was given), and this task doesn't
add a create endpoint either. That's a real gap for whoever builds the next
piece (a Format management endpoint, or a seed update once the
pillar→format mapping is decided).

`PATCH` is a first for this codebase (every other resource uses `PUT` for
partial updates, e.g. `PUT /videos/{id}`, `PUT /publish-logs/{id}`) --
used here because the task's own endpoint list specified it explicitly.

## Verification

Script-driven (`TestClient`, real lifespan, temp SQLite DB) covering every
endpoint: pillars list (6 seeded), formats list + pillar filter (including
a nonexistent-pillar-id filter returning `[]` not an error), idea create
validation (bad pillar/format/emotion id, format/pillar mismatch, blank
title, invalid status), get + 404, list filters (pillar/format/status/
score range) + pagination (`page`/`page_size`), patch (partial update,
invalid status, 404), delete (204, subsequent 404, 404 on missing id), and
a final re-fetch confirming all mutations persisted. Also re-checked
`/health`, `/videos`, `/publish-logs`, `/categories` still return 200 to
confirm nothing existing broke. All checks passed.
