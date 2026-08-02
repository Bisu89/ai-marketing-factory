# 11 — Video Composer (multi-clip merge with transitions + narration/subtitles)

**Commits:** `6132627` (initial, included TTS narration + burned-in karaoke
subtitles), `a232130` (drag-and-drop uploads + clip thumbnails), `aae37da`
(temporarily dropped TTS/karaoke, added output-folder picker), current
commit (restored narration/karaoke-subtitles, plus: a single uploaded clip
now skips the merge ffmpeg pass entirely instead of running a no-op
scale/pad through it).

## What it does

Lets a user merge several uploaded video clips into one finished video from
the web UI: upload clips (click or drag-and-drop), reorder them, add a
title + a script, optionally add background music, optionally pick a
destination folder, and get back a single video with:

- a swipe-left transition between every pair of clips (not a hard cut) --
  skipped when there's only one clip (see "The ffmpeg pipeline" below),
- a fixed title overlay at the top,
- Spanish TTS narration (`edge-tts`) generated from the typed script,
- burned-in karaoke-style subtitles timed to the narration (toggleable),
- optional background music mixed under the narration (looped/trimmed to
  the video's length).

Runs as a background job (`queued` → `merging` → `narrating` →
`subtitling` → `mixing_audio` → `finalizing` → `completed`/`failed`),
polled by the frontend every 2s -- same shape as
[10-scene-cutter.md](10-scene-cutter.md) and the History page's download
polling.

This started as a port of an `edge-tts`+ffmpeg pipeline from a standalone
`ghep_video.py` script (pasted by the user), including Spanish TTS
narration and burned-in karaoke subtitles. That stage was temporarily
removed ("tạm thời chỉ cần ghép video... xóa phụ đề với karaoke đi") to
ship a simpler version first, then explicitly restored once
output-folder-picking and drag-and-drop had landed on top of the simplified
version -- the data model and service were left in a shape that made
re-adding it a matter of restoring the removed methods/fields, not a
redesign.

## Architecture

`app/modules/video_composer/` -- a self-contained vertical slice per the
extensibility convention in
[06-extensibility-eventbus.md](06-extensibility-eventbus.md) /
`app/modules/README.md`: own models, schemas, service (own queue + worker
thread, independent of `DownloadEngine` and `SceneCutterService`), own
`APIRouter`. No FK into the core `Video`/`Channel` schema -- these are
standalone compositions, not Library videos.

Single worker thread, same rationale as Scene Cutter: the pipeline is
ffmpeg encoding work, and this runs on one desktop for one user.

## Data model

- `video_compose_job` -- one row per composition: `title`, `script_text`,
  `voice` (default `es-ES-AlvaroNeural`, not user-selectable from the UI),
  `music_path` (nullable), `music_volume`, `transition_duration`,
  `burn_subtitles`, `requested_output_dir` (nullable -- user's custom
  destination folder, same convention as `SceneCutJob.requested_output_dir`),
  `status`, `output_path`, `subtitle_srt_path`, `error_message`, timestamps.
- `video_compose_clip` -- one row per input clip: `job_id` FK, `position`
  (0-based merge order), `file_path`. Position is derived purely from the
  order files arrive in the multipart `files[]` field -- the frontend
  reorders its local list with up/down buttons before submit, then appends
  files to `FormData` in that final order; multipart parsers preserve
  field order, so no separate ordering payload is needed.

No Alembic yet (see [05-database-normalization.md](05-database-normalization.md)):
restoring the `NOT NULL` `script_text` column (dropped in the simplification)
can't be done with a plain `ALTER TABLE` either, so the dev tables were
dropped and recreated by `Base.metadata.create_all()` again -- same
precedent as the original catalog normalization and the simplification
commit before this one.

## The ffmpeg pipeline

1. **Merge with transitions** (skipped entirely for a single clip): each
   clip is scaled/padded to the first clip's resolution and fps, then
   chained through ffmpeg's `xfade` filter (`transition=slideleft`).
   `xfade` requires a computed `offset` per transition
   (`cumulative_duration_so_far - transition_duration`); the transition
   duration is clamped to at most half the shortest clip's length so the
   offset math can't go negative on a very short clip. When there's only
   one uploaded clip there's nothing to transition into, so this step is
   skipped outright -- `merged_video` is just the original upload passed
   straight through to narration/subtitling/finalize, rather than running
   it through a no-op scale/pad/re-encode pass first (faster, and keeps
   the source quality). Original per-clip audio is dropped (`-an`) when a
   real merge does run -- narration replaces it, and mixing each clip's own
   audio across an `xfade` transition would need a matching `acrossfade`,
   not worth it for audio that gets discarded anyway.
2. **Narrate**: `edge_tts.Communicate(script, voice, boundary="WordBoundary")`
   streams synthesized speech to `narration.mp3` while collecting
   per-word `(start, end, text)` timestamps from the `WordBoundary` events
   -- these timestamps are what makes the subtitles karaoke-timed instead
   of just line-timed.
3. **Subtitle**: words are grouped into display lines (breaks on a >0.6s
   gap, >5 words, or >4.5s of accumulated duration) and written as an ASS
   karaoke file (`\k` per-word highlight tags, a random color per line from
   a fixed palette) plus a plain `.srt` alongside it for reference.
4. **Mix audio**: narration is padded to the merged video's duration
   (`apad` + `-t`); if music was provided it's looped (`-stream_loop -1`),
   volume-adjusted, and mixed in under the narration.
5. **Finalize**: title `drawtext` (and `subtitles=...` burn-in, if
   `burn_subtitles`) applied to the merged video in one filter chain, muxed
   with the mixed audio track.

Intermediate files (`merged.mp4`) live under
`library/_video_composer/job_<id>/tmp/` and are deleted once the job
finishes (success or failure). The final video lives at
`library/_video_composer/job_<id>/output/video_hoan_chinh.mp4` by default,
or directly inside the user's chosen folder with no `job_<id>` nesting if
`requested_output_dir` was given -- same reasoning as Scene Cutter: once a
user explicitly picks a destination, an extra unrequested subfolder layer
would be surprising.

## Endpoints

```
POST /video-compose-jobs                multipart: title, script, voice,
                                         files[] (ordered), music? (optional),
                                         music_volume, transition_duration,
                                         burn_subtitles, output_dir?
GET  /video-compose-jobs                list all jobs
GET  /video-compose-jobs/{job_id}       status
POST /video-compose-jobs/{job_id}/open-folder
POST /video-compose-jobs/pick-folder    native folder-picker dialog, returns {path}
```

`pick-folder` pops a server-side `tkinter` directory dialog, same mechanism
and same Windows-only reasoning as Scene Cutter's identical endpoint (see
[10-scene-cutter.md](10-scene-cutter.md)'s design-decisions section) --
duplicated rather than imported, since `app/modules/README.md` disallows a
module importing another module.

## Frontend

Sidebar entry "Video Composer" (`/video-composer`,
`frontend/src/pages/VideoComposerPage.tsx`): a "Thêm video..." multi-file
picker (click to browse, or drag files in from Explorer) whose selections
accumulate into a reorderable list -- up/down/remove buttons per row, each
showing an actual decoded video-frame thumbnail (a muted `<video>` on a
`URL.createObjectURL(file)` blob) rather than just the filename, since
Scene-Cutter-output filenames are opaque random hex and hard to tell apart
when reordering. Below that: title input, a script textarea (Spanish, used
for narration + subtitles), optional music file (also drag-and-drop-able) +
volume, an output-folder field (typed, or filled in via "Chọn thư mục..."),
transition-duration, a "Chèn phụ đề vào video" checkbox, and submit. A
polled job list shows the current phase in Vietnamese and, once completed, a real
`<video>` preview (only when the output is servable via `/media`, i.e. no
custom folder was picked outside `library_dir`) plus a "Mở thư mục" button.

## Verification

Real end-to-end tests against the actual backend (not mocked) at each
stage of this feature's evolution:

- Original TTS+karaoke version: confirmed `edge-tts` genuinely reaches
  Microsoft's TTS service from this environment, then verified a 3-clip
  merge (red/blue/green) reached `completed` with the correct total
  duration, a visually-confirmed swipe-left transition (extracted the
  mid-transition frame), a rendered title, and karaoke subtitle lines with
  real TTS-derived timing; also verified reordering, background music,
  disabling subtitle burn-in, and the single-clip (no-transition) path.
- Drag-and-drop + thumbnails: verified with real synthetic `drop` events
  carrying an actual `File` built from real bytes (Playwright has no
  built-in OS file-drag simulation). Caught a real bug this way -- the
  first thumbnail implementation created the blob URL in a `useState` lazy
  initializer with revocation in a separate cleanup-only effect, which
  React 19 StrictMode's dev-only mount→cleanup→mount replay broke (every
  thumbnail rendered solid black); fixed by creating and revoking the
  object URL within the same effect invocation.
- Current (post-simplification) version: re-ran the pipeline via curl for
  both the with-music and without-music branches -- confirmed the
  without-music output has exactly one stream (`codec_type=video`, no
  audio at all, not a silent track) and the with-music output has both
  streams; confirmed a custom `output_dir` receives the file directly with
  no `job_<id>` subfolder. Confirmed via Playwright that the script
  textarea and subtitle checkbox are actually gone from the DOM (not just
  visually hidden), and that a real job submitted through the UI with a
  custom output folder completes successfully.
- All test jobs, output files, and DB rows removed afterward -- except one
  real job the user had already created through their own testing
  (`"B L A C K"`, 5 clips) before this simplification's schema change
  required dropping the table; that DB row was lost, but the actual
  finished video file on disk was left untouched.
- Narration/subtitles restoration + skip-merge-for-single-clip: `ffmpeg`/
  `ffprobe` were not installed on this machine at all (`where ffmpeg` found
  nothing) -- installed via winget (`Gyan.FFmpeg`) before any of this could
  be tested; a first job submission after that install still failed with
  `[WinError 2] The system cannot find the file specified` because the
  already-running backend process's PATH predated the install -- restarting
  it (from a shell with a refreshed PATH) fixed it. With that resolved, ran
  real jobs against the actual backend (synthetic 3s red/blue clips, real
  Spanish script, real `edge-tts` calls): a 2-clip job completed with a
  correct 5.5s duration (3+3-0.5s transition overlap), an AAC audio track,
  and a real TTS-timed `.srt`/`.ass` pair; a 1-clip job completed in ~1.2s
  (vs ~1.6s+ for the 2-clip job) with output duration exactly 3.000s
  matching the source clip precisely -- confirming the merge ffmpeg pass is
  genuinely skipped, not just its transition effect; a job with
  `burn_subtitles=false` completed with narration intact. All 3 test jobs'
  DB rows and output directories were removed afterward. Also surfaced
  (not fixed, flagged to the user instead) that `library_dir` currently
  points at `data/library/youtube` rather than `data/library` -- likely
  picked by mistake through the Settings folder-browser -- since that's a
  user configuration choice, not something to silently revert.
