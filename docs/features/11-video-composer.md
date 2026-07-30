# 11 — Video Composer (multi-clip merge with transitions)

**Commits:** `6132627` (initial, included TTS narration + burned-in karaoke
subtitles), `a232130` (drag-and-drop uploads + clip thumbnails), `aae37da`
"Simplify Video Composer: drop TTS/karaoke, add output-folder picker"
(current shape).

## What it does

Lets a user merge several uploaded video clips into one finished video from
the web UI: upload clips (click or drag-and-drop), reorder them, add a
title, optionally add background music, optionally pick a destination
folder, and get back a single video with:

- a swipe-left transition between every pair of clips (not a hard cut),
- a fixed title overlay at the top,
- optional background music mixed in (looped/trimmed to the merged video's
  length) -- if no music is given, the output has no audio track at all.

Runs as a background job (`queued` → `merging` → `finalizing` →
`completed`/`failed`), polled by the frontend every 2s -- same shape as
[10-scene-cutter.md](10-scene-cutter.md) and the History page's download
polling.

This started as a port of an `edge-tts`+ffmpeg pipeline from a standalone
`ghep_video.py` script (pasted by the user), including Spanish TTS
narration and burned-in karaoke subtitles. The narration/subtitle stage was
then explicitly removed again ("tạm thời chỉ cần ghép video... xóa phụ đề
với karaoke đi") to keep the feature to just clip merging for now; nothing
in the data model or service prevents adding an opt-in narration/subtitle
step back later.

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

- `video_compose_job` -- one row per composition: `title`, `music_path`
  (nullable), `music_volume`, `transition_duration`, `requested_output_dir`
  (nullable -- user's custom destination folder, same convention as
  `SceneCutJob.requested_output_dir`), `status`, `output_path`,
  `error_message`, timestamps.
- `video_compose_clip` -- one row per input clip: `job_id` FK, `position`
  (0-based merge order), `file_path`. Position is derived purely from the
  order files arrive in the multipart `files[]` field -- the frontend
  reorders its local list with up/down buttons before submit, then appends
  files to `FormData` in that final order; multipart parsers preserve
  field order, so no separate ordering payload is needed.

No Alembic yet (see [05-database-normalization.md](05-database-normalization.md)):
since this schema change removed a `NOT NULL` column (`script_text`) that
a plain `ALTER TABLE` can't relax, the dev tables were dropped and
recreated by `Base.metadata.create_all()` rather than migrated in place --
same precedent as the original catalog normalization.

## The ffmpeg pipeline

1. **Merge with transitions**: each clip is scaled/padded to the first
   clip's resolution and fps, then chained through ffmpeg's `xfade` filter
   (`transition=slideleft`). `xfade` requires a computed `offset` per
   transition (`cumulative_duration_so_far - transition_duration`); the
   transition duration is clamped to at most half the shortest clip's
   length so the offset math can't go negative on a very short clip. A
   single clip skips `xfade` entirely. Original per-clip audio is dropped
   (`-an`) -- there's no narration anymore to justify keeping a separate
   audio pipeline, and mixing each clip's own audio across an `xfade`
   transition would need a matching `acrossfade`, which isn't worth it for
   audio nobody asked to keep.
2. **Finalize**: title `drawtext` applied to the merged video. If a music
   file was provided, it's looped (`-stream_loop -1`), volume-adjusted, and
   muxed in with `-shortest` (so it doesn't extend the video); otherwise
   the output is encoded with `-an` -- no audio track, not a silent one.

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
POST /video-compose-jobs                multipart: title, files[] (ordered),
                                         music? (optional), music_volume,
                                         transition_duration, output_dir?
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
when reordering. Below that: title input, optional music file (also
drag-and-drop-able) + volume, an output-folder field (typed, or filled in
via "Chọn thư mục..."), transition-duration, and submit. A polled job list
shows the current phase in Vietnamese and, once completed, a real
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
