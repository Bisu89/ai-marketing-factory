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
18. [Narration language option](features/18-narration-language-option.md) — AI Story + Video Composer switch from hardcoded Spanish to a language/voice picker (English default)
19. [Beat domain contract](features/19-beat-domain-contract.md) — framework-independent Beat/BeatPlan Pydantic contract for the future Video Factory, serialized to `beats.json`, no DB table yet
20. [Asset module](features/20-asset-module.md) — self-contained local asset library (register/tag/search/lookup image/video/audio files) for the future Video Factory
21. [Motion domain and presets](features/21-motion-domain-presets.md) — deterministic, declarative Ken-Burns-style motion contract + 9 presets for the future Video Factory, no rendering yet
22. [Composition contract](features/22-composition-contract.md) — declarative `CompositionPlan`/`Scene` contract combining beat/asset/motion/caption/audio into a renderable plan, no rendering, no module-to-module imports
23. [Local motion renderer](features/23-local-motion-renderer.md) — turns a still image + MotionPlan into an MP4 via a local ffmpeg Ken-Burns pipeline, no AI video generation, no cloud service
24. [Composition ↔ Video Composer integration](features/24-composition-video-composer-integration.md) — renders a CompositionPlan's image scenes via the motion renderer and hands them to video_composer's existing, unmodified pipeline through a new adapter endpoint
25. [Video Factory audio + caption pipeline](features/25-video-factory-audio-captions.md) — configurable narration volume, real sidechain music ducking, fade in/out, optional per-scene SFX cues, and 5 caption presets, extending video_composer's existing audio mixer and ASS caption renderer
26. [Video Factory frontend workflow](features/26-video-factory-frontend.md) — a single new page (script → beats → assets → captions/audio → render → output) driving the existing backend pipeline end-to-end; verified with a real Playwright run against a real render
27. [Video Factory golden sample](features/27-video-factory-golden-sample.md) — a canonical example project (5 beats, 30s, 5 motion presets, captions, narration, music) proving the Beat/Asset/Motion/Composition contracts compose correctly, with chain-integrity tests, before any end-to-end rendering exists
28. [Video Factory end-to-end pipeline](features/28-video-factory-e2e-pipeline.md) — enforced local-only rendering policy, lightweight render metadata/cost tracking, and a real ffprobe-verified render of the golden sample proving Story→Beat→Asset→Motion→Composition→FFmpeg→final.mp4 works end to end

## Keeping this up to date

See the "Documentation" section in `CLAUDE.md` at the repo root — every
completed feature gets a new file under `features/`, numbered next in
sequence, and a line added to the list above.
