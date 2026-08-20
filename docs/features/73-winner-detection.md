# 73. Content Winner Detection

**Commit:** `06404f9`

Statistically-aware "which content pattern actually performs better"
analysis, built directly on Task 07's `PerformanceService.all_performances()`
-- no metric computed twice. Covers pillar/format/hook/story style/
platform/duration, with a configurable minimum-sample-size gate so a
single video is never called a "winner."

## Normalization ("do not simply rank by raw views")

`VideoPerformance` (Task 07) gained 3 new fields, all resolved from data
already on hand:

- `share_rate` (shares/views) -- the task's own explicitly-required metric,
  missing from Task 07's per-video output.
- `views_per_day_since_publish` -- publication-age normalization: views
  divided by days live as of the snapshot's own upload time (not "now" --
  a historical snapshot must report the same rate every time it's read
  back). Distinct from Task 07's `view_velocity_per_day` (growth *between
  two snapshots*, a different question).
- `platform_relative_views` -- "account/platform context" normalization:
  each video's views expressed as a multiple of *its own platform's*
  average linked views (new `apply_platform_relative_views()`, run once
  per `all_performances()` call). A platform with fewer than 2 linked
  videos has no computable baseline; those videos get a `None` with a
  note rather than a fabricated ratio.

New `app/services/insights/winner_detection_service.py`
(`WinnerGroupStats`/`compute_group_stats`) builds each group's
`performance_score` from 60% platform-relative views (capped at 3x that
platform's average, so one viral post can't carry a whole group) + 40%
engagement rate -- falling back to the video's own raw-views-based
`performance_score` (Task 07) only when platform-relative isn't
computable yet, and saying so in the group's `note`.

## Minimum sample size

`min_sample_size` (default 5, the task's own example) is a real query
parameter on every endpoint, not hardcoded. Each `WinnerGroupStats`
carries `meets_minimum_sample` + a `confidence` tier
(`insufficient`/`low`/`medium`/`high`, scaled off the threshold) --
callers are expected to gate "winner" language on `meets_minimum_sample`,
never just sort-and-take-the-top. Groups below threshold are still
returned (never silently dropped), with a note explaining why they can't
be called a winner yet.

## Duration

Bucketed with `app.services.library.repository.DURATION_BUCKETS` (the
exact buckets the Library page's own duration filter already uses) rather
than a second bucketing scheme.

## Rising / Underperforming Formats

Two different, deliberately distinct definitions:

- **Rising** -- a real *time trend*: a group's members are split at the
  median `published_at` into an earlier and a more recent half (each half
  needing its own minimum sample to mean anything), and "rising" requires
  the recent half's average `performance_score` to be ≥15% higher than the
  earlier half's. Groups where either half is too small return
  `insufficient_data` rather than a guessed direction.
- **Underperforming** -- an *absolute standing* comparison (no time split
  needed): formats that meet the minimum sample whose `performance_score`
  sits below the average across every format that also meets the minimum
  -- the bottom tier of a real, apples-to-apples comparison.

## API (all read-only)

`GET /winners/{formats,hooks,story-styles,platforms,duration,pillars}`
(`?min_sample_size=`), `GET /winners/formats/rising`,
`GET /winners/formats/underperforming`. Pillar/format again need the
composition-root cross-module join (`_pillar_format_by_log`, imported
directly from `performance_intelligence.py` rather than duplicated --
same "composition roots reuse each other's small helpers" precedent
`content_batch_generate.py` already established for
`content_idea_generation.py`).

## UI

New page `/winners` (`WinnerDetectionPage.tsx`) -- 5 sections exactly as
asked (Top Formats/Hooks/Pillars, Rising/Underperforming Formats), a
shared configurable min-sample-size input, reusing the pre-existing,
previously-unused `BarRanking` component (built in an earlier task,
never wired to a real page until now) plus a stats table with confidence
badges. A brand new, focused page -- the existing Production Dashboard
was not touched.

## Verification

Real, hand-crafted dataset (not the trivial 2-3-row cases from earlier
tasks): 2 formats × 6 posts each (one genuinely improving over time, one
genuinely declining and overall weaker), 2 platforms with real baselines
(12 Facebook + 2 TikTok posts) plus 1 never-linked post, spread across
published dates from -60 to -5 days. All endpoints hit for real:

- **Top Formats**: "Betrayal" correctly ranked first (score 30.4 vs
  12.7), `avg_views`/`median_views` exactly matched hand-computed values.
- **Rising Formats**: "Betrayal" correctly flagged rising (+186.7%,
  matching its designed improving trend); "Mother Story" correctly
  absent.
- **Underperforming Formats**: "Mother Story" correctly flagged (below
  the 2-format average); "Betrayal" correctly absent.
- **Top Platforms**: TikTok (2 linked) correctly showed
  `meets_minimum_sample: false` + `confidence: "insufficient"` at the
  default threshold of 5; re-querying with `min_sample_size=2` flipped it
  to eligible and bumped Facebook's confidence to `"high"` -- proving the
  threshold is genuinely configurable, not just accepted and ignored.
- **Duration buckets**: posts landed in the exact expected buckets
  (`30-60`, `<30`, `1-3min`) matching their real `duration_sec` values.
- **Never-linked post**: appeared in `sample_size` counts everywhere it
  belonged but never in `linked_sample_size` or any average -- never
  silently dropped, never guessed.
- Regression: Task 07's `/performance/videos` and `/performance/formats`
  (old shape) still return correct, unaffected results.
- Real Playwright browser run: all 5 sections render with real data
  matching the API responses exactly, threshold input re-fetches
  correctly, zero console errors.

`python -c "import app.main"` and `npx tsc -b --noEmit` both clean.
Existing dev servers on 8000/5173 untouched.
