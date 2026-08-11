# AI Content Library — Documentation

Desktop-local content library for short-form video: paste a URL, detect the
platform, download, and manage the result in a searchable library (categories,
tags, favorites, status). FastAPI backend + React/TypeScript frontend +
SQLite.

## Start here

- [Architecture](architecture.md) — layers, folder structure, how the pieces fit together
- [Database](database.md) — every table and how they relate

## Features (chronological)

1. [Project scaffold](features/01-project-scaffold.md) — FastAPI + React + SQLite, config/logging/DI
2. [App shell UI](features/02-app-shell-ui.md) — Sidebar, Dashboard/Download/Library/History/Settings pages
3. [Download Engine](features/03-download-engine.md) — queue, pause/resume/retry/cancel, parallel downloads, progress
4. [Library organizer](features/04-library-organizer.md) — auto-organize completed downloads into `library/<platform>/<channel>/<video_id>/`
5. [Catalog normalization](features/05-database-normalization.md) — Video/Channel/Playlist/DownloadTask/DownloadHistory, dedup by (platform, external_id)
6. [Extensibility (EventBus)](features/06-extensibility-eventbus.md) — decoupled hook point for future modules (subtitles, captions, voice, etc.)
7. [Real detection & download via yt-dlp](features/07-detection-download-ytdlp.md) — replaces the mocked URL analysis with real yt-dlp extraction and download
8. [Library backend API](features/08-library-backend-api.md) — Repository/Service layers, `/videos` `/categories` `/tags` REST endpoints, search/filter/sort/pagination
9. [Library frontend UI](features/09-library-frontend-ui.md) — Grid/Table views, video cards, preview drawer, static media serving
10. [Scene Cutter](features/10-scene-cutter.md) — automatic scene-detection video splitting (PySceneDetect + ffmpeg), background job + polling UI
11. [Video Composer](features/11-video-composer.md) — merge multiple uploaded clips with swipe-left transitions, title overlay, optional background music
12. [Content Workflow](features/12-content-workflow.md) — editable status/topic/emotion/tags/notes in the Library drawer, plus real search & filter
13. [AI Story](features/13-ai-story.md) — Claude Sonnet 5 generates 2 Spanish marketing narration script variants per video, synchronous (no background job)
14. [Desktop packaging](features/14-desktop-packaging.md) — PyInstaller + pywebview + Inno Setup turn the app into a no-admin Windows installer, with bundled ffmpeg
15. [Performance Intelligence, Phase 1](features/15-performance-intelligence.md) — links Insights CSV data to real Library videos (PublishLog), real-data dashboard by topic/emotion/hook/story-style, winners/losers
16. [AI Content Platform](features/16-ai-content-platform.md) — unified `app/modules/ai` (Story relocated + new Hook/Caption generators), shared Claude client + generation history
17. [Karaoke highlight box](features/17-karaoke-highlight-box.md) — trend-style captions: white text always, colored box slides behind the active word instead of recoloring it

## Keeping this up to date

See the "Documentation" section in `CLAUDE.md` at the repo root — every
completed feature gets a new file under `features/`, numbered next in
sequence, and a line added to the list above.
