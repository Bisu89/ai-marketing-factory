# 07 — Real detection & download via yt-dlp

**Commit:** `cb22294` "Wire real yt-dlp downloads and download status/history UI"

## What it does

Replaces the client-side mock from
[02-app-shell-ui.md](02-app-shell-ui.md) with real platform detection and
real downloads: pasting a YouTube/TikTok/Facebook/Instagram URL now actually
extracts real metadata and downloads the real file.

## Detection

`app/services/detect/ytdlp_detector.py` runs
`yt_dlp.YoutubeDL(...).extract_info(url, download=False)` with
`extract_flat="in_playlist"` (metadata only, no bytes fetched). Platform is
guessed from the URL via regex (youtube.com/youtu.be, tiktok.com,
facebook.com/fb.watch, instagram.com); content type is `channel` if the URL
looks like a channel path, `playlist` if yt-dlp reports a playlist entry
type, otherwise a single `video`. Exposed as `POST /api/v1/detect`
(`app/api/v1/endpoints/detect.py`).

## Download

`app/services/download/ytdlp_downloader.py` implements the same `Downloader`
interface from [03-download-engine.md](03-download-engine.md), so it drops
into `DownloadEngine` unchanged (`main.py` now constructs
`DownloadEngine(downloader=YtdlpDownloader(), ...)` instead of
`HttpDownloader()`). Key difference from the generic HTTP downloader:
yt-dlp owns its own output filename (needs the real extension), so it
downloads to `f"{destination}.%(ext)s"` and the produced file is moved onto
the engine's expected `destination` path once finished. Pause/cancel is
signaled through yt-dlp's `progress_hooks`, raising yt-dlp's own
`DownloadCancelled` internally and re-raising as this project's
`DownloadPaused`/`DownloadCancelled` depending on which event fired. Resume
relies on yt-dlp's own `.part` file + `continuedl: True`, keyed off the same
deterministic destination stem -- the engine's `resume_from` byte offset
isn't used here (yt-dlp manages its own resume state).

## Frontend

- `src/api/detect.ts`, `src/api/downloads.ts` — real API calls replacing
  `src/mock/analyzeUrl.ts` (deleted)
- `DownloadPage.tsx` — calls `detectUrl()`/`enqueueDownload()` instead of the
  mock
- `HistoryPage.tsx` — live-polls `GET /downloads` every 2s, shows per-task
  status (including in-progress `%`) and an "Open folder" action once
  complete (a second, task-scoped open-folder endpoint,
  `POST /downloads/{task_id}/open-folder` -- distinct from the
  video-scoped one added in
  [08-library-backend-api.md](08-library-backend-api.md); both coexist,
  each serving its own page)

## Note

This landed from a separate concurrent Claude Code session while Sprint V8
(Library) was in progress in another session; merged via `git merge` with
manual conflict resolution in `main.py` / `router.py` / `client.ts` (both
sides had added compatible-but-overlapping code -- CORS, router
registration, API helpers). See the merge commit `9b64444`.
