# 139. Viral Source Radar (Phase 1)

One search box that fans a topic ("beard transformation") out to every
platform in parallel, normalizes + dedups + rule-scores the results, and
shows them in a grid with Open / Save / (rights-gated) Download. No AI, no
paid API for a normal search.

**Landed in:** _uncommitted at time of writing_ — feat: Viral Source Radar Phase 1

**Key files**
- `backend/app/modules/discovery/` — `engines/` (reddit + youtube real;
  tiktok + instagram honest "unavailable" stubs), `keywords.py`
  (deterministic topic-dictionary expansion), `scoring.py` (views/
  engagement/recency/relevance/short-form/content-signal, weights
  renormalized over whatever metrics a platform actually exposes),
  `dedup.py` (URL + title-similarity grouping, `also_on`), `orchestrator.py`
  (thread-pool fan-out, one engine failing never sinks the search),
  `service.py` (persist + 15-min in-process cache + Save system),
  `models.py` (`discovery_search` / `discovery_result`), `router.py`.
- `backend/alembic/versions/0002_viral_source_radar.py`
- `backend/app/core/config.py` — `youtube_api_key`, `reddit_client_id/secret`
  (+ `update_*` + `PUT /settings/youtube-api-key` / `/settings/reddit-credentials`)
- `frontend/src/pages/RadarPage.tsx` (+ `/radar` route, sidebar link,
  `api/discovery.ts`, `types/discovery.ts`)
- `frontend/src/pages/DownloadPage.tsx` — now reads `?url=` so a Radar
  card's "Tải" opens the existing download flow pre-filled.

**Non-obvious decisions**
- **TikTok / Instagram are stubs on purpose.** Neither has a public
  keyword-search API a distributed desktop app may use (TikTok Research API
  = approved institutions only; Display/Graph APIs = the caller's own
  account). The brief forbids defeating anti-bot measures, so the engines
  report `unavailable` with a reason rather than scraping. Only these two
  files change if that ever changes.
- **YouTube quota is the real ceiling, not $.** `search.list` is 100 units
  of a 10k/day free quota, so the orchestrator caps YouTube at 3 expanded
  queries (Reddit at 6); a 403 stops the engine and returns partial results
  instead of hammering the API.
- **Rights default to UNKNOWN.** Download is offered only for YouTube
  Creative Commons (+ stored attribution) in Phase 1; everything else shows
  "Cần xin phép" and no Download button.
- Reddit exposes no view count, so its engagement component is simply
  dropped and its weight redistributed — a Reddit post is not punished for
  a metric the platform doesn't have.
- Own tables, no FK/relationship into other modules (same shape as
  `news` / `content_batch`); this module must never import
  `app.modules.beat` / `batch` / `ai`.

**Verified:** 34 module tests (expansion, scoring graceful-degradation,
dedup grouping, orchestrator failure isolation, unavailable stubs, rights →
download-capability gating, service persist/save/find-similar) + a
TestClient smoke of `POST /discover` → save → `GET /discover/saved`.
