# 09 — Library frontend UI (Sprint V8, Milestone 3)

**Commit:** `fb75990` "Sprint V8 Milestone 2+3: Library backend APIs and frontend UI"

## What it does

Replaces the Library page placeholder with a real, working library browser:
Grid/Table view toggle, video cards/rows with the full field set (thumbnail,
title, channel, platform, duration, resolution, size, download date, status,
category, tags, favorite, Open Folder / Copy URL / Preview actions),
URL-param-driven pagination, and a read-only preview drawer with a real
`<video>` player.

Editing (status/category/tags/notes) from the drawer, real-time search, and
the full filter sidebar are intentionally **not** here yet -- see the
milestone plan in [database.md](../database.md) history / project memory;
they're separate milestones (Preview, Search, Filters) so each lands as a
reviewable increment.

## Key files

```
src/api/videos.ts                          fetch wrappers for /videos, /categories
src/features/library/
  types.ts                                  VideoOut, VideoListResponse, etc. (mirrors backend schema)
  hooks/useVideos.ts                        TanStack Query, keepPreviousData for smooth pagination
  hooks/useCategories.ts
  hooks/useVideoMutations.ts                favorite toggle, open-folder (optimistic-ish via invalidate)
  components/{VideoCard,VideoTable,VideoGrid,ViewToggle,StatusBadge,Pagination,VideoDetailDrawer}.tsx
src/pages/LibraryPage.tsx                   orchestrates the above; page/view state in the URL
```

State: TanStack Query for server data (added as a new dependency this
milestone); page/view-mode in `useSearchParams` (shareable, survives
refresh, no extra state library needed); `selectedVideoId` for the drawer is
local component state.

## Required backend additions (not scope creep -- the UI can't work without them)

- **Static file serving** (`/media`, mounted onto `library_dir`) +
  `thumbnail_media_url`/`video_media_url` computed fields on `VideoOut`.
  `thumbnail_path`/`video_path` are server filesystem paths; a browser
  `<img>`/`<video>` tag can't load those directly.
- **CORS middleware** — first time frontend and backend actually talked to
  each other for real (earlier pages were all client-mocked).
- **`POST /videos/{id}/open-folder`** — opens the OS file explorer via
  `os.startfile` (Windows) / `open` (macOS) / `xdg-open` (Linux); safe from
  injection since the path comes from the DB, never client input.

## Bugs caught during real-browser verification (Playwright)

1. CORS was hardcoded to `http://localhost:5173` — broke immediately when
   the dev server happened to start on a different port (5183, in this
   case, since 5173 was busy). Fixed with `allow_origin_regex` matching any
   localhost port.
2. `mediaUrl()` didn't percent-encode path segments — a channel name with a
   space ("Adventure Vlogs") produced a broken image URL. Fixed by encoding
   each path segment.

## Verification method

Playwright (headless Chromium) driven against the real dev server + real
backend + a locally seeded video (via the real `/downloads` flow, not
fixtures): screenshotted grid view, table view, and the drawer; asserted
zero console errors; drove an actual favorite-toggle click end to end and
asserted the UI reflected the real mutated backend state.
