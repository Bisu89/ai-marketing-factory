# 72. Performance Intelligence

**Commit:** `pending`

Read-only analytics: real published-post performance (views/likes/
comments/shares/follower conversion/engagement rate/view velocity/a
computed performance score), joined against the creative metadata that
produced each video, answering the task's 7 required questions (top
videos, top hooks, top story styles, top pillars, top formats, by
platform, over time).

## Restoring Insights

This task's brief assumed `insight_upload`/`insight_post_snapshot` still
existed. They were deleted in the same "remove AI Content + Insights"
pass as Task 63 and never restored since (unlike `ai/story`/`ai/hook`,
restored in Task 04). Asked the user directly; chose to restore the data
layer (models, CSV parser, `InsightService`, the `/insights/*` endpoints)
but **not** the frontend `/insights` page. Also restored
`PublishLogService.link_to_post`/`unlink`/`list_unlinked_posts` and the
corresponding `publish-logs/{id}/link-post`/`unlink` endpoints + the
`views`/`interactions`/`post_id`/`page_id` fields on `PublishLogOut` --
without these, `post_id`/`page_id` could never be set on any `PublishLog`
at all, which would make every performance metric permanently null for
every row, not just the ones genuinely never linked.

## No duplicate analytics system, no duplicated lifetime metrics

New `app/services/insights/performance_service.py` (`PerformanceService`,
`VideoPerformance`, `DimensionPerformance`) is **core-only** -- it never
imports `content_strategy`/`ai.story`, so it lives as a plain service, not
a composition root. It resolves every number live from the latest
`InsightPostSnapshot` on every call (via the restored
`publish_log_service.latest_snapshot_for`/new `all_snapshots_for`) --
nothing is stored twice. "Performance over time" reuses the pre-existing
`InsightService.get_trend()` outright rather than re-implementing it.

New composition root `app/api/v1/endpoints/performance_intelligence.py`
is the only place allowed to import `app.services.insights` together with
`app.modules.ai.story` and `app.modules.content_strategy` -- needed only
for Top Pillars/Top Formats, which trace
`PublishLog.ai_story_job_id -> StoryJob.content_idea_id (Task 04) ->
ContentIdea.pillar_id/format_id`. Every other endpoint is a thin
pass-through to `PerformanceService`.

## Metrics: computed vs. honestly null

- **views/comments/shares/reactions/saves/real_followers** -- straight
  from the latest linked snapshot.
- **engagement_rate** = `interactions / views`; **follower_conversion_rate**
  = `real_followers / views` -- both `null` (with a note) when views is 0
  or the post was never linked.
- **view_velocity_per_day** -- `(latest.views - first.views) / days`
  across the *first and latest* of every snapshot on file for that post.
  Requires **2+ real, dated snapshots**; with only 1 (the common case for
  a post uploaded just once), returns `null` with an explicit note --
  never a fabricated rate from a single point.
- **performance_score** -- a documented, transparent heuristic (60% a
  views component capped at 100k, 40% engagement rate), computed only
  when real views exist; every response also carries
  `performance_score_note` stating plainly it's an internal ranking
  heuristic, not a platform-provided number.
- **Top pillars/Top formats** -- real today only for `PublishLog` rows
  whose `ai_story_job_id` points at a `StoryJob` with `content_idea_id`
  set (Task 04's bridge). Since the frontend picker for `ai_story_job_id`
  was removed in Task 63 and never restored, this chain is broken for
  most real `PublishLog`s today -- groups with no resolvable pillar/format
  are excluded (not guessed), and every `DimensionPerformance` carries
  `sample_size` vs `linked_sample_size` so a group's real data coverage is
  never hidden.

## Verification

Real CSV upload flow end to end (not synthetic snapshot rows inserted
directly) via `POST /insights/upload`, two uploads 5 days apart (to get a
real 2-snapshot view-velocity case), 4 `PublishLog`s covering every data
state: fully linked with 2 snapshots (velocity computable), linked with 1
snapshot (velocity null + reason), linked with real content-idea
provenance (pillar/format resolve), and never linked at all (every metric
null + reason). All 7 endpoints hit for real:

1. **Top videos** -- correct descending `performance_score` order, the
   unlinked video last with every field `null` and `data_note` explaining
   why (never silently dropped).
2. **Top hooks** / **3. Top story styles** -- correct grouping/sample
   sizes, `linked_sample_size` correctly lower than `sample_size` when a
   group includes an unlinked log.
3. **Top pillars** / **Top formats** -- the real cross-module join
   resolved "Love"/"Betrayal" for exactly the one log with a real
   Idea-driven `StoryJob`; every other log correctly excluded (no
   resolvable pillar/format), not guessed.
4. **By platform** -- correct per-platform totals, `instagram` (the
   unlinked log's platform) correctly shown with `total_views: null` +
   explanatory note instead of 0.
5. **Over time** -- exact per-upload view/interaction sums matched the
   source CSVs (15,500/1,115 then 28,000/2,400).

Regression: `/insights/summary`, `/insights/unlinked-posts`,
`/publish-logs/{id}` (views/interactions enrichment), `link-post`
(rejects a post already linked elsewhere with 400, accepts a genuinely
free one), `unlink` -- all still correct. `/videos`, `/categories`,
`/content-pillars` unaffected. `python -c "import app.main"` clean.
Existing dev servers on 8000/5173 untouched.
