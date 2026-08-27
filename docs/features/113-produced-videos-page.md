# 113. Produced Videos page — browse every finished render

**Commit:** _(fill in after commit)_

Real user report: there was no single screen to see the videos the
Factory produces. The Dashboard only showed a short "Recent Videos"
strip, Video Factory is strictly per-project, and Batch detail is
per-batch — so a finished video was hard to find again and there was no
way to browse the whole catalogue.

## What it does

New `/videos` page (sidebar entry "Videos"): a thumbnail grid of every
`VideoComposeJob` render — Factory and classic Video Composer alike —
with:

- Status tabs (Hoàn thành / Lỗi / Tất cả) + Batch, Series and title-search filters
- Cards: `thumbnail.jpg`, title (project name, falling back to the
  Packaging `metadata.json` title, then the job title), duration badge,
  batch/series + date
- Click → drawer with an inline `<video>` player, the AI-written
  description/hashtags, resolution/size/render-time/date, links to the
  batch/series, the output path (copyable), and "Mở thư mục" (reveals the
  output folder — same server-resolved-path desktop pattern as
  `videos.open_folder` / `downloads` open-folder), plus "Mở trong Video
  Factory"

Read-only otherwise — no delete/re-render/metadata-edit (deliberately
scoped out with the user).

## Key files

- `app/api/v1/endpoints/produced_videos.py` (new) — composition root:
  `GET /produced-videos` (joins video_composer + beat + batch + series,
  none of which import each other, like `dashboard.py`) and
  `POST /produced-videos/{id}/open-folder`. Facets (batches/series with
  video counts) are computed over the status-filtered set so the dropdowns
  offer every selectable value, not just what survives the current filter.
- `app/api/v1/router.py` — router registration
- `frontend/src/pages/VideosPage.tsx` / `.css` (new)
- `frontend/src/api/producedVideos.ts`, `frontend/src/types/producedVideo.ts` (new)
- `frontend/src/App.tsx`, `frontend/src/components/Sidebar.tsx` — route + nav

## Non-obvious decisions

- **Project link is dual**: a job is tied to a project via
  `Project.render_job_id` (single-project / Factory) *or*
  `BatchItem.render_job_id` (batch flow). The endpoint checks both.
- **`Query()` objects avoided**: the endpoint uses plain parameter
  defaults + manual clamping (like `dashboard.build_dashboard`) so it stays
  directly unit-testable without going through FastAPI dependency
  resolution.

## Verification

`tests/api/test_produced_videos.py` (6 tests: empty, batch-item link,
status filter, batch/search filter, standalone-project link, pagination)
+ `test_dashboard.py` green. `npx tsc -b --noEmit` and `npm run build`
clean. Live `GET /produced-videos` against the real dev DB returned 76
completed / 90 total with correct batch/series facets; `open-folder`
returned 204 and opened the folder. No browser tool was available this
session to screenshot the page itself — verified via the clean build and
by mirroring `SeriesPage`/`LibraryPage` drawer + `Pagination` patterns.
