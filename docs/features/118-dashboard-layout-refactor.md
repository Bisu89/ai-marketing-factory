# 118. Production Dashboard: Layout Refactor

**Commit:** `abad324`

Real user request to refactor the dashboard's layout. Same data, same
endpoint ([43](43-production-dashboard.md)) — this is purely a
frontend re-layout for a clearer read.

## Before → after

The old page was 9 same-weight cards stacked vertically (KPIs, Current
Production, Currently Rendering, Needs Attention, Render Queue, Recent
Videos, Recent Failures, Production Pipeline, Today's Rendering) — lots of
scroll, no hierarchy.

New order follows what a producer opens the dashboard to check:

1. **KPI strip** — Ready / Needs review / Blocked (only when >0) /
   Rendering / Done today. A zero count stays quiet; a non-zero one lights
   its accent edge.
2. **Needs attention** — one panel merging the attention list **and**
   recent render failures (both are "something's wrong"), sorted
   BLOCKED → FAILED → NEEDS_REVIEW, with a red left border. Hidden
   entirely when there's nothing wrong (no more empty card).
3. **Running now** — a 2-column row: "Running now" (current batch progress
   *and* the current render, or an idle note) + "Render queue".
4. **Recent videos** — unchanged list + a new "All videos" link to the
   `/videos` page ([113](113-produced-videos-page.md)).
5. **At a glance** — Pipeline breakdown + Today's numbers folded into one
   muted, low-emphasis card instead of two full cards at the bottom.

## Key files

- `frontend/src/pages/DashboardPage.tsx` / `.css` (only these)

No backend, no type, no API change.

## Verification

`npx tsc -b --noEmit` and `npm run build` clean. No browser tool this
session to screenshot; the component reuses the page's own existing
card/list/chip styles and `PageHeader`/`EmptyState`/`NewVideoModal`
untouched.
