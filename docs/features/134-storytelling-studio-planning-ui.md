# 134. AI Storytelling Studio — Phase 2 (planning UI)

The first frontend surface for the Studio: a `/studio` page to create and
list stories, and a `/studio/:storyId` detail page to drive the planning
pipeline and review the Scene Director + cost estimate.

## What it does

- **`/studio`** — story list + a "New Story" modal (title, mode, logline,
  genre, budget cap; a reference-notes field appears for HISTORY /
  EDUCATION).
- **`/studio/:storyId`**:
  - **Run panel** — one card that reflects the latest `StoryRun`:
    - no run → "Run planning" button
    - active → a 6-stage stepper (Development → Story bible → Characters →
      Chapters → Scenes → Scene Director + cost), polled every 1.6 s, with
      Cancel
    - `FAILED` → the failed stage + `error_message` + Retry
    - `NEEDS_REVIEW` + `error_code === "COST_GUARD_BLOCKED"` → the
      estimate-vs-cap numbers and a "new budget cap" input; "Raise cap &
      retry" `PATCH`es `budget_usd` then retries (with a note when the cap
      actually comes from the project config's cost guard, not the budget
      field)
    - `READY` → done, with a Re-run button
  - **Pre-flight cost bar** — total vs cap, verdict pill
    (`OK`/`WARN`/`BLOCK`/`UNKNOWN`), per-component breakdown, notes.
  - **Cast** — generated characters with their locked
    `canonical_prompt_block`.
  - **Scenes per chapter** — a table per chapter: narration, type, the
    four sub-scores + composite, and a `STILL` / `STILL_WITH_MOTION` /
    `AI_VIDEO` badge. A `<select>` overrides the visual mode (sets
    `visual_mode_source = "USER"`, which freezes it against a re-run); a
    "locked ✕" button hands the scene back to the Scene Director.
  - **Re-run Scene Director** — `POST /classify-scenes` + refresh.

## Key files

- **New:** `src/pages/StudioPage.tsx`, `src/pages/StudioStoryPage.tsx`,
  `src/pages/StudioPage.css` (shared by both), `src/api/story.ts`,
  `src/types/story.ts`
- **Modified:** `src/App.tsx` (2 routes), `src/components/Sidebar.tsx`
  (nav entry, `NotebookPen` icon)

## Non-obvious decisions

- **`PUT /story-scenes/{id}` replaces the whole scene** (`StorySceneIn`,
  `extra` forbidden), so `updateScene` in `api/story.ts` rebuilds the full
  input from the loaded scene and applies just the override — the page
  never hand-maintains a partial-patch shape.
- **The detail page loads scenes per chapter, not via `/scene-plan`.** It
  needs the full `StoryScene` objects (narration, all the fields
  `updateScene` must send back) that `/scene-plan` deliberately trims;
  cost comes from a separate `/cost-estimate` call.
- **Plain `useState`/`useEffect` + a `refresh()` + a single active-run
  poll timer** — matches `ProductionProgress` / `SeriesDetailPage` exactly
  rather than introducing a TanStack Query layer this page doesn't need.

## Verification

`npx tsc -b --noEmit` clean; `npm run build` succeeds. Headless-Chrome DOM
dump against a real backend: `/studio` lists a seeded story; `/studio/1`
renders the detail page — title, logline, the Planning-pipeline card, the
6-stage stepper, the "Run planning" button. Run start/fail/retry paths are
the same endpoints already HTTP-verified in feature 133.

## Landed in

`TBD`
