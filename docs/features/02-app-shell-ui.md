# 02 — App shell UI

**Commit:** `44d8b21` "Sprint 2: build app shell UI (Sidebar, Dashboard, Download, Library, History, Settings)"

## What it does

The navigable app frame: a sidebar with five routes and a page per route.
At this stage the Download page's URL analysis was **mocked client-side**
(`src/mock/analyzeUrl.ts` guessed platform/content-type from the URL string
and returned fake video data) since there was no backend detection service
yet -- replaced by real yt-dlp detection in
[07-detection-download-ytdlp.md](07-detection-download-ytdlp.md).

## Key files

- `src/layouts/AppShell.tsx` + `src/components/Sidebar.tsx` — sidebar + routed
  content area
- `src/pages/{Dashboard,Download,Library,History,Settings}Page.tsx` — one
  page per sidebar item
- `src/components/{VideoResultCard,ChannelVideoTable,PlatformBadge,EmptyState,PageHeader}.tsx`
  — shared building blocks: single-video result card, channel/playlist result
  table with per-video checkboxes + a download-count limit input, a platform
  color badge, an empty-state placeholder, and a page header with an actions
  slot
- Global CSS variables in `src/index.css` (light/dark aware) that every later
  feature reuses rather than redefining

## Notable decisions

- Design system: plain CSS files per component (no CSS-in-JS, no Tailwind) --
  matches the project's preference for minimal dependencies.
- State: local component state only at this stage; server state (TanStack
  Query) wasn't introduced until [09-library-frontend-ui.md](09-library-frontend-ui.md)
  once there was a real backend to talk to.
