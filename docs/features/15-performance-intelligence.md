# 15 — Performance Intelligence, Phase 1 (link real performance data to videos)

**Commit:** `4ab46f4` "Performance Intelligence Phase 1: link real
performance data to videos".

## What it does and why

Answers "why did this video do well?" with real numbers, not guesses. The
user pasted a very large "Performance Intelligence" spec (full dashboard,
automatic insights, a recommendation engine, an "AI learning" knowledge
base, per-video report pages, global search, affiliate analytics) framed as
a brand-new module. Before building anything, this app already had a
working, non-trivial piece of the same problem: `app/services/insights/` —
CSV import of Meta Business Suite's "Content" export, with summary/top-posts/
trend already built (`InsightsPage.tsx`). It just wasn't connected to
anything else — `InsightPostSnapshot` is keyed by Facebook's own `post_id`,
with no link to `video.id`, and none of the new dimensions the spec wanted
(topic/emotion/hook/story-style/affiliate) existed anywhere.

Per the user's explicit choices: **upgrade the existing Insights pipeline,
don't build a parallel system**; AI/affiliate metadata is captured via a
**manual "Publish Log" form** (the CSV export has no such columns, and
hand-editing the CSV before every upload is fragile); and this is
**Phase 1 only** — the Recommendation Engine and "AI Learning" knowledge
base are explicitly deferred, since they need a real corpus of linked,
published videos to reason over. Building them now would just be empty
logic with nothing to learn from.

## The link: `PublishLog`, keyed by `post_id`/`page_id`, not per-snapshot

`backend/app/models/publish_log.py` — a new core model (`video_id` FK,
platform, page_name, hook_type, story_style, `ai_story_job_id`, affiliate_*,
published_at, status, `post_id`/`page_id`, notes).

Two design decisions worth calling out:

1. **Linking is keyed by `post_id`+`page_id`, not a `video_id` column added
   to `InsightPostSnapshot`.** A real-world post gets a *new*
   `InsightPostSnapshot` row on every CSV re-upload (growth tracking over
   time — see that model's own docstring). `post_id` is the one thing
   stable across all of them, so linking once at that level covers every
   past *and future* snapshot automatically. This needed **zero schema
   changes** to the existing `InsightUpload`/`InsightPostSnapshot` tables.
2. **Linking is an explicit user action** ("Gắn với bài viết" on the
   Insights page), not auto-matching by title text. A `PublishLog` is
   usually created *before* any matching CSV data exists (the user can't
   upload their own Facebook post from inside this app), so fuzzy title
   matching would be fragile and fail silently. A small picker is reliable
   and is exactly the judgment call a human already has to make.

**`ai_story_job_id` is a plain nullable `int`, not an ORM relationship.**
Per `app/modules/README.md`, core must never import from a module, and
`StoryVersion` lives in `app.modules.story`. Rather than bend that rule, the
frontend resolves the AI Story link itself: `PublishLogSection.tsx` calls
the **already-existing** `GET /story-jobs?video_id=` (from Epic 13) when the
form opens, lets the user pick a version, and pre-fills `story_style` from
that version's `job.style` — zero new backend coupling.

## Backend

- `app/models/publish_log.py`, `app/schemas/publish_log.py` (new).
- `app/services/insights/publish_log_service.py` (new) — CRUD +
  `link_to_post()`/`unlink()`. `latest_snapshot_for(post_id, page_id)` is
  the shared helper (also used by `performance_service.py`) that resolves
  "the current numbers for this post" by ordering
  `InsightPostSnapshot.id.desc()` (equivalent to ordering by the parent
  upload's `uploaded_at`, since rows are always inserted in upload order —
  simpler than an extra join).
- `app/services/insights/performance_service.py` (new) — aggregates by
  fetching every linked `PublishLog`, resolving each one's latest snapshot,
  and **grouping in Python** (not SQL) by topic/emotion/hook_type/
  story_style. Matches the existing `InsightService.get_by_post_type`'s own
  style; the expected data volume (one creator's own published videos)
  doesn't warrant more than that.
- `app/api/v1/endpoints/publish_log.py`, `.../performance.py` (new); one
  addition to the existing `.../insights.py`: `GET /insights/unlinked-posts`.
- Wired into `app/api/deps.py` and `app/api/v1/router.py` the same way every
  other service/router in this app is.

## Frontend

- **"Log Publish" lives on `VideoDetailDrawer`** (Epic 12's existing drawer)
  via a new `PublishLogSection.tsx` — the natural place, since the user is
  already looking at the video's own metadata there. Shows any existing
  publish logs (with real linked stats, if linked) and a form to add one.
- **Insights page gets a second tab**, "Performance Intelligence", instead
  of a new nav entry — matches "upgrade, don't fragment". The existing CSV
  tab gained an "unlinked posts" section with a per-row video picker.
- **New `BarRanking` component** (`frontend/src/components/BarRanking.tsx`)
  for the topic/emotion/hook/story-style breakdowns — read the `dataviz`
  skill first, per its trigger conditions. Per the skill's own form-choice
  table ("compare magnitude, low → high" → bar chart, sequential/one-hue
  color job), these are single-metric rankings across categories, not
  multi-series comparisons — so they use one consistent `var(--accent)` fill
  rather than a categorical palette (which would need the skill's
  colorblind-safety validator; a single-hue magnitude ranking doesn't).
  Winners/Losers, being multi-attribute records rather than a single
  magnitude, are a table instead, per the same form-choice guidance.

## Verification

Real data through the full pipeline, not simulated:

- Imported two real Library videos with deliberately different
  topic/emotion (Comedy/Vui vs. Military/Kịch tính), created a `PublishLog`
  for each with different hook_type/story_style.
- Uploaded a real Meta-export-shaped CSV (exact Vietnamese headers the
  existing `csv_parser.py` expects) through the **unmodified** existing
  upload endpoint, with `post_id`/`page_id` chosen to match — one post
  seeded at 9,000 views, the other at 1,200, specifically so a correctness
  bug (e.g. reversed sort, wrong join) would be visible immediately rather
  than passing by coincidence.
- Confirmed both posts appeared in `GET /insights/unlinked-posts`; linked
  each via `POST /publish-logs/{id}/link-post`; confirmed the response
  correctly resolved `views: 9000/interactions: 900` and
  `views: 1200/interactions: 150` respectively.
- Confirmed `GET /performance/overview` ranked Comedy over Military, Vui
  over Kịch tính, "Beard + Surprise" over "Wife Reaction", and "humorous"
  over "dramatic" — all correctly by real total views, not insertion order.
- Confirmed `GET /performance/winners` / `/losers` ranked the two videos in
  the correct (opposite) order.
- Confirmed the **duplicate-link guard**: attempting to link an
  already-linked `post_id` to a different `PublishLog` returns a clean `400`
  ("Bài đăng này đã được gắn với một video khác."), not a silent overwrite.
- Confirmed `unlink()` correctly returns the post to
  `GET /insights/unlinked-posts`.
- Confirmed `GET /story-jobs?video_id=` (Epic 13's endpoint, reused
  unmodified) returns cleanly for a video with zero AI Story generations —
  `PublishLogSection` correctly hides the version picker in that case.
- `tsc -b` type-checks clean; Vite's dev server transforms every new/changed
  module (`InsightsPage.tsx`, `BarRanking.tsx`, `PublishLogSection.tsx`,
  `VideoDetailDrawer.tsx`, `publishLog.ts` API + types) without error. As
  with recent features, no browser-automation tool was available this
  session, so the rendered UI itself was not visually confirmed — the user
  should click through it once with a real backend running.
- All test videos, publish logs, and the test CSV upload were deleted
  afterward; every endpoint confirmed back to an empty state before
  finishing.
