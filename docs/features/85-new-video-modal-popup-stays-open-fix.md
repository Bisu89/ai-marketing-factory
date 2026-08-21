# 85. Fix: "Generate Full by AI" Popup Stayed Open on Video Factory Page

**Commit:** (pending)

Real user report: creating a video via `NewVideoModal` from the Video
Factory page's "Generate Full by AI" button left the popup open on
screen even though the project was created successfully underneath.

## Root cause

`handleSubmit`/`handleGenerateFullByAI` (`frontend/src/components/
NewVideoModal.tsx`) never called `onClose()` -- they only called
`navigate(/video-factory?project=<id>)`. On the Dashboard (a different
route) this was invisible: navigating away unmounts the whole page,
taking the modal with it. Reused on `VideoFactoryPage` itself (see
docs/features/83), the target route is the *same* one already showing
-- React Router only updates the query param, it doesn't unmount the
route element, so the modal (controlled by a parent `aiNewVideoOpen`
boolean that only `onClose` ever flips) stayed mounted on top of the
now-updated page.

## Fix

Call `onClose()` right before `navigate(...)` in both handlers -- safe
on Dashboard too (already unmounting anyway).

## Verification

Playwright against the real running app: opened Video Factory page,
clicked "Generate Full by AI", unchecked "Produce automatically" (so
only `createProject` runs -- no FactoryRun/AI spend), submitted, and
confirmed the `.nvm-backdrop` element is gone and the URL updated to the
new project id. `npx tsc -b --noEmit` clean.
