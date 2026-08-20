# 66. Content Studio Frontend (Pillar → Format → Idea)

**Commit:** `pending`

First UI for Task 22/23's Content Strategy API: a new `/content-studio`
page (`frontend/src/pages/ContentStudioPage.tsx`), reusing existing
patterns throughout -- `PageHeader`, `EmptyState`,
`features/library/components/Pagination` (extended with an optional
`itemLabel` prop, default unchanged, so Library still reads "N video"),
`features/library/hooks/useEmotions`, the `.btn`/`.btn-primary` global
classes, and the TanStack Query hook shape from `features/library/hooks/`.
New `features/contentStudio/` (types.ts, hooks/, components/IdeaCard.tsx)
mirrors that folder's structure. `api/client.ts` gained `apiPatch` -- the
first PATCH caller on the frontend, needed because Task 22's
`PATCH /content-ideas/{id}` was itself the first PATCH endpoint in this
codebase.

## What "Generate Ideas" actually does

No AI provider and no bulk-generate endpoint exist yet (both explicitly out
of scope). "Generate Ideas" calls `POST /content-ideas` in a loop, N times,
creating N `status: "draft"` ideas titled `Ý tưởng mới #1..N` against the
chosen Pillar/Format -- then the review list is filtered to exactly what
was just created. Each `IdeaCard` is inline-editable (title, premise,
target emotion, commercial intent, score) with an explicit "Lưu" button
that only appears once a field is actually dirty, so these placeholder
drafts are immediately usable as a real manual workflow, not a dead end
waiting for AI. This is stated in-page (a hint line under the Generate
button) so it isn't a silent surprise.

## Known gap surfaced in the UI, not hidden

Format has no seed data and no create endpoint (Task 22 note). If a
Pillar's Format dropdown is empty, the page shows an inline message
("Pillar này chưa có Format nào...") instead of a silently-empty,
confusing dropdown.

## Verification

- `npx tsc -b --noEmit` -- clean.
- Real browser run (Python Playwright driving Chromium, since neither
  `chromium-cli` nor a JS Playwright install were available in this repo)
  against an isolated `uvicorn` (port 8001) + `vite` (port 5180) pair on a
  throwaway SQLite DB -- did **not** touch the two dev servers already
  running on 8000/5173 (not started by this session). Screenshots +
  assertions covered: empty state, cascading Pillar→Format dropdowns,
  generating 3 drafts (confirmed via real `POST` 201s in the server log),
  inline edit + Save + a full page reload confirming SQLite persistence,
  per-card status change, the review filter bar (pillar/format/status/
  min-score) narrowing results, checkbox selection + bulk "Từ chối",
  delete, and `/dashboard` still rendering normally afterward.
  `console --errors` equivalent (Playwright `console`/`pageerror` listeners)
  was empty throughout.
