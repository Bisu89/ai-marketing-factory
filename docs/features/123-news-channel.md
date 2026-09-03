# 123 — News Channel: RSS Ingestion → Drafted Script → Batch

**Commit:** `92fbe21`

Adds the missing front end for a news channel: pull articles from RSS/Atom
feeds, let the user pick which ones become videos, AI-draft a straight
news-read narration script per article, then hand a selection off to the
existing Batch pipeline. Semi-automatic by design — nothing is rendered
without the user selecting it (product decision, for factual-accuracy
control).

```
RSS feed → NewsItem (deduped) → [user selects] → draft-script (AI) → /news/batch
        → Project (script locked) + Batch → existing generate-beats / render-all
```

## New module: `app/modules/news/`

- `models.py` — `NewsSource` (a feed URL + label + language + enabled) and
  `NewsItem` (one deduped article: title/summary/link/image/published_at,
  a `status` lifecycle `new → drafted → queued → used`/`dismissed`, plus
  bare `project_id`/`batch_id` ints set once a video is made). Own tables,
  no FK into any other module — same isolation rule as `content_strategy`.
- `feeds.py` — pure fetch+parse adapter. `httpx` does the network call
  (consistent timeout/error handling); `feedparser` only ever sees
  downloaded bytes. HTML stripped from summaries, entry count capped at 40.
- `service.py` — `SessionLocal`-per-call functions (same shape as
  `batch.service`, callable from the background poll thread). Dedup is
  two-layer: per-source on the feed entry `guid`, and **across all
  sources** on a normalized-title fingerprint (the same wire story
  syndicated to two feeds is not turned into two videos).
- `seed.py` — a small VN starter set (VnExpress, Tuổi Trẻ) so "Fetch all"
  works on first open. Idempotent, same shape as `seed_default_pillars`.
- `router.py` — `/news/sources` CRUD, `/news/sources/{id}/fetch`,
  `/news/fetch-all`, `/news/items` (list + filter), `PATCH /news/items/{id}`.

## Composition root: `app/api/v1/endpoints/news_pipeline.py`

The one place allowed to import `news` + `beat` + `batch` + `ai` together
(leans on `batch_render.py` for template lookup + `BatchOut`).

- `POST /news/items/draft-scripts` — one structured LLM call per item:
  headline + summary → `{hook, body[], ending}` flattened to `script_text`.
  Prompt hard-constrains to "report only what the source states, no
  invented quotes/numbers/names, neutral anchor tone, no CTA". Synchronous
  for ≤3 items, backgrounded (bounded by `max_concurrent_ai_generation`,
  shared AI semaphore) above that.
- `POST /news/batch` — mirrors `create_batch`'s script path exactly (one
  shared session, `Project` + `Batch` + `BatchItem` committed once). The
  drafted script becomes a non-blank `Project.script_text`, which is the
  Factory CONTENT stage's own skip condition — so the news wording is
  preserved whether the batch is driven by classic generate-beats or the
  Factory batch engine. Items flip to `queued` with their `project_id`/
  `batch_id` recorded.

## Built-in template: `NEWS_VI_TEMPLATE` (`news_vi`)

7th built-in. Vietnamese, `vi-VN-NamMinhNeural` (male anchor, edge_tts),
`top` caption preset, barely-there `SLOW_PUSH_IN`/`SUBTLE` motion, very low
music bed (0.08), `target_duration` 45s, `cta_enabled=False`. Carries only
look + voice — never any editorial stance.

## Background poll loop

`main.py` gains a `news-feed-poll` daemon thread, same shape as the
render-cache sweep: a no-op while `settings.news_poll_interval_minutes == 0`
(shipped default), re-checks the setting every 5 min, otherwise re-fetches
every enabled source on that interval.

## Frontend

New `/news` page ("Tin tức" in the sidebar): a collapsible Sources panel
(add / enable-toggle / per-source fetch / delete) and a status-tabbed item
feed with multi-select → "Tạo script" / "Tạo Batch" (small modal for
name + template, defaults to `news_vi`, then navigates to the batch page).

## Key files

- `backend/app/modules/news/` (new), `backend/app/api/v1/endpoints/news_pipeline.py` (new)
- `backend/app/core/config.py` — `news_poll_interval_minutes` + updater
- `backend/app/api/v1/endpoints/settings.py` — `GET /settings` field + `PUT /settings/news-poll-interval`
- `backend/app/main.py` — seed call + poll loop
- `backend/app/api/v1/router.py` — router registration
- `backend/app/modules/beat/schemas.py` — `NEWS_VI_TEMPLATE`
- `backend/requirements.txt` / `AIContentLibrary.spec` — `feedparser==6.0.14` (+ `sgmllib` hidden import)
- `frontend/src/pages/NewsPage.tsx` + `.css`, `api/news.ts`, `types/news.ts`, `App.tsx`, `Sidebar.tsx`

## Verification

`pytest tests/modules/news tests/api/test_news_pipeline.py` (14) green —
feed parsing, guid + cross-source fingerprint dedup, feed-error recording,
draft-script fills + locks, `/news/batch` builds projects and queues items,
unknown-template rejection. `tests/modules/beat` updated for the 6→7
builtin count. `npx tsc -b --noEmit` clean. Not run against live feeds /
a real LLM key in this pass (mocked at the module boundary, same
convention as the content-stage tests).

## Follow-up: article images + digest ("điểm tin")

Commit `5230fd1`. Two additions after the first cut:

- **`app/modules/news/images.py`** — `prepare_article_image()`: httpx
  download → PIL cover-crop (`ImageOps.fit`, centering 0.5/0.4) to the
  exact render-profile size → JPEG. Cover-crop not letterbox: a landscape
  news photo would otherwise waste ~60% of a vertical frame. Rejects
  non-images and sub-320px thumbnails (soft — caller falls back).
- **`POST /news/batch` gains `use_article_image` (default true)** — when
  on, each item's RSS photo is downloaded + registered as an
  `Asset(source="news_image")`, and the project's beats are **pre-built
  deterministically** from the drafted script's paragraphs (one beat each,
  every beat pointing at that photo), `BatchItem → BEATS_READY`, no AI
  beat split / no library match. Download failure → falls back to the
  plain `script → Generate Beats` path (`PROJECT_CREATED`).
- **`POST /news/digest`** — one roundup video from 2–15 items. A single
  structured LLM call → `{intro, segments:[{narration}]×N, outro}` from
  the items' own headlines/summaries (faithful, neutral, no CTA). Builds
  **one** project directly: HOOK(intro) + BODY(segment)×N + ENDING(outro),
  each segment beat showing that story's own photo. One 1-item Batch, all
  N news items → `queued` → that project.
- Both produce through the **Factory engine** (`POST /batches/{id}/
  factory-run`, called by the frontend right after create) — the classic
  Render All path hardcodes an English voice; the Factory GENERATING_VOICE
  stage uses the template's real voice (`vi-VN-NamMinhNeural`).
- **Quality Gate**: `source == "news_image"` joins `"ai_image_generator"`
  in the confidence short-circuit (`quality_gate.py`) — an article photo
  has no tags/filename to keyword-match a headline-derived `visual_hint`,
  so without this every news video sat at `NEEDS_REVIEW` forever.
- Frontend: "Dùng ảnh từ bài viết" checkbox + a "Tạo bản điểm tin" button
  on the select bar → shared `CreateModal` (batch|digest).
- Verified live: real VnExpress digest (3 stories → 5 beats, 3 real photos
  cover-cropped to 1080×1920, `news_image` assets, `script_locked`).

## Not built (deliberate)

News API adapters (paid, keyed) — RSS only for now. Full auto-pilot
(poll → draft → render with no human step) — the poll loop and draft
endpoint exist, but wiring them into an unattended render was scoped out
for factual-accuracy reasons. Commentary/reaction script style — the
template only does a straight read.
