# 11 — Video Composer (multi-clip merge, transitions, TTS narration, karaoke subtitles)

**Commit:** `6132627` "Add Video Composer: multi-clip merge with
transitions, TTS narration, karaoke subtitles"

## What it does

Lets a user merge several uploaded video clips into one finished video from
the web UI: upload clips, reorder them, add a title and a Spanish script,
optionally add background music, and get back a single video with:

- a swipe-left transition between every pair of clips (not a hard cut),
- a fixed title overlay at the top,
- Spanish narration generated from the typed script via `edge-tts`,
- burned-in karaoke-style subtitles synced to the narration's own
  word-boundary timing (falls back to plain, non-burned `.srt` alongside),
- optional background music mixed under the narration.

Runs as a background job (`queued` → `merging` → `narrating` →
`subtitling` → `mixing_audio` → `finalizing` → `completed`/`failed`),
polled by the frontend every 2s -- same shape as
[10-scene-cutter.md](10-scene-cutter.md) and the History page's download
polling.

This ports the ffmpeg + `edge-tts` pipeline from a standalone
`ghep_video.py` script (pasted by the user) into a real in-app feature, per
an explicit follow-up request: multi-video upload with reordering, a
swipe-left transition (the original script only did a hard-cut `concat`),
and title/script as web form fields instead of a folder + a `.txt` file.

## Architecture

`app/modules/video_composer/` -- another self-contained vertical slice per
the extensibility convention in
[06-extensibility-eventbus.md](06-extensibility-eventbus.md) /
`app/modules/README.md`: own models, schemas, service (own queue + worker
thread, independent of `DownloadEngine` and `SceneCutterService`), own
`APIRouter`. No FK into the core `Video`/`Channel` schema -- these are
standalone compositions, not Library videos.

Single worker thread, same rationale as Scene Cutter: the whole pipeline
(ffmpeg encoding, TTS network call) is either CPU-bound or a single
sequential network request, and this runs on one desktop for one user.

## Data model

- `video_compose_job` -- one row per composition: `title`, `script_text`,
  `voice` (edge-tts voice id, defaults to `es-ES-AlvaroNeural`, not
  exposed as a picker in the UI yet), `music_path` (nullable),
  `music_volume`, `transition_duration`, `burn_subtitles`, `status`,
  `output_path`, `subtitle_srt_path`, `error_message`, timestamps.
- `video_compose_clip` -- one row per input clip: `job_id` FK, `position`
  (0-based merge order), `file_path`. Position is derived purely from the
  order files arrive in the multipart `files[]` field -- the frontend
  reorders its local list with up/down buttons before submit, then appends
  files to `FormData` in that final order; multipart parsers preserve
  field order, so no separate ordering payload is needed.

## The ffmpeg pipeline

1. **Merge with transitions**: each clip is scaled/padded to the first
   clip's resolution and fps, then chained through ffmpeg's `xfade` filter
   (`transition=slideleft`) rather than the original script's `concat`
   filter. `xfade` requires a computed `offset` per transition
   (`cumulative_duration_so_far - transition_duration`); the transition
   duration is clamped to at most half the shortest clip's length so the
   offset math can't go negative on a very short clip. A single clip skips
   `xfade` entirely (no transition to build). Original per-clip audio is
   dropped (`-an`) -- the final output's audio track is entirely the
   generated narration (+ optional music), matching the source script's own
   behavior (it also only ever mapped the separately-mixed audio into the
   final output, never the concatenated clips' own audio).
2. **Narration**: `edge_tts.Communicate(script, voice, boundary="WordBoundary")`
   streamed to an mp3, collecting each word's start/end offset.
3. **Subtitles**: words are grouped into karaoke lines (break on a >0.6s
   gap, 5 words, or 4.5s of line duration -- ported unchanged from the
   source script), each rendered as an `.ass` `\k`-tagged karaoke line
   (random color per line from a fixed palette) plus a plain `.srt` for
   reference/upload elsewhere.
4. **Audio mix**: narration `apad`-ed to fill dead air, optionally `amix`-ed
   with looped background music at a configurable volume, trimmed to the
   merged video's duration.
5. **Finalize**: title `drawtext` + (if enabled) `subtitles=` burn-in
   applied to the merged video, muxed with the final mixed audio track,
   `libx264`/`aac`, `-shortest`.

Intermediate files (`merged.mp4`, `narration.mp3`, `mixed_audio.m4a`) live
under `library/_video_composer/job_<id>/tmp/` and are deleted once the job
finishes (success or failure); the final video and both subtitle files
stay in `library/_video_composer/job_<id>/output/`.

## Endpoints

```
POST /video-compose-jobs                multipart: title, script, files[] (ordered),
                                         music? (optional), music_volume, transition_duration,
                                         burn_subtitles, voice
GET  /video-compose-jobs                list all jobs
GET  /video-compose-jobs/{job_id}       status
POST /video-compose-jobs/{job_id}/open-folder
```

## Frontend

Sidebar entry "Video Composer" (`/video-composer`,
`frontend/src/pages/VideoComposerPage.tsx`): a "Thêm video..." multi-file
picker whose selections accumulate into a reorderable list (up/down/remove
buttons per row, not native drag-and-drop -- simpler to get right and just
as usable for a handful of clips), title input, script textarea, optional
music file + volume, transition-duration and burn-subtitles controls, and
submit. Below it, a polled job list showing the current pipeline phase in
Vietnamese and, once completed, a real `<video>` preview of the final
composed file plus a "Mở thư mục" button.

## Verification

Real end-to-end tests against the actual backend (not mocked), confirming
edge-tts genuinely reaches Microsoft's TTS service from this environment
before relying on it:

- 3-clip merge (red/blue/green) via curl: confirmed `completed` status,
  correct total duration (`3+3+3 - 2×0.5s transition = 8s`), and visually
  verified by extracting frames -- the mid-transition frame actually shows
  the slide-left effect (old clip sliding left, new clip entering from the
  right), the title renders, and karaoke subtitle lines appear with real
  TTS-derived timing matching the typed script.
- 2-clip job with reversed order + background music + `burn_subtitles=false`:
  confirmed the *reversed* order took effect in the actual output (second
  clip appeared first), music mixing didn't error, and no subtitle text was
  burned in (while the `.srt`/`.ass` files were still written, matching the
  source script's behavior of always generating them).
- Single-clip job: confirmed the no-transition code path doesn't error.
- Full browser test (Playwright, real Vite dev server + real backend):
  added two clips via the multi-file input, used the up-arrow button to
  reorder the second clip to first, submitted with a real title/script,
  polled to "Hoàn tất — 2 video", and confirmed the rendered preview's
  first frame is actually the reordered (originally-second) clip's color --
  proving the reorder UI genuinely changes the output, not just the list
  display. Zero console errors.
- All test jobs, output files, and DB rows removed afterward.
