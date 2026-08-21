# 93. Fix: Completed AI Render Didn't Show Until Manual Refresh

**Commit:** `b38e3bb`

Real user report: after "Generate Full by AI" finished rendering, the
page didn't show it -- only F5 revealed the completed video.

Reproduced with a real Playwright run against the running app: with the
tab kept active/focused the whole time, the page auto-updated correctly
(auto-navigates to Step 5, shows the finished video, zero reload) the
instant the backend reported COMPLETED -- so the polling itself works.
The gap is specifically when the tab is backgrounded/inactive (very
plausible for a multi-minute render -- the user switches away to do
something else while waiting): browsers throttle `setInterval`/
`setTimeout` in inactive tabs (can slow to once a minute or less), and
switching back to the tab doesn't reset that timer -- it just waits out
whatever's left of the throttled delay.

## Fix

Added a `document.visibilitychange` listener to both polling loops
involved in showing render progress -- `ProductionProgress.tsx`'s own
FactoryRun poll and `VideoFactoryPage.tsx`'s render-job poll -- firing an
immediate poll the instant the tab becomes visible again, without
changing the steady-state poll cadence.

## Verification

Real Playwright run: simulated a backgrounded-then-foregrounded tab
(`document.visibilityState`/`hidden` + a real dispatched
`visibilitychange` event, matching what a real browser fires) and
confirmed both endpoints (`GET /projects/{id}/factory-run` and `GET
/video-compose-jobs/{id}`) get an immediate real network request within
500ms of visibility returning.

## Note: same pattern exists elsewhere, not touched here

`DashboardPage.tsx`, `BatchDetailPage.tsx`, `ContentBatchDetailPage.tsx`,
`HistoryPage.tsx`, `SceneCutterPage.tsx`, `VideoComposerPage.tsx`,
`AssetLibraryPage.tsx`, and `ReadyToPostCard.tsx` all have their own,
separate `setInterval`/`setTimeout` polling loops with the same
theoretical exposure. Scoped this fix to the two loops actually involved
in the reported "Generate Full by AI" scenario rather than touching
every polling loop in the app unasked.
