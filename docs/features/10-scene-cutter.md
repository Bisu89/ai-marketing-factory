# 10 — Scene Cutter (automatic scene-detection video splitting)

**Commit:** `ca44c91` "Add Scene Cutter: background scene-detection video
splitting feature"

## What it does

Lets a user cut a video into per-scene clips from the web UI, using
PySceneDetect (content-aware cut detection) + ffmpeg (actual splitting),
without leaving the app or touching a terminal. Source can be either an
existing Library video or an arbitrary local file path the user types in.
Runs as a background job (`queued` → `analyzing` → `splitting` →
`completed`/`failed`) so a multi-minute video doesn't block the request or
the UI; the frontend polls job status every 2s, same pattern as the History
page's download polling.

This wraps the same detection/splitting logic already written as the
standalone `tools/cat_canh.py` script (an interactive-menu CLI tool added
earlier the same day), now exposed as a real in-app feature per the user's
follow-up request.

## Architecture

Built as `app/modules/scene_cutter/` -- a self-contained vertical slice per
the extensibility convention in
[06-extensibility-eventbus.md](06-extensibility-eventbus.md) /
`app/modules/README.md`: own models, own schemas, own service (with its own
queue + worker thread, *not* sharing `DownloadEngine`), own `APIRouter`.
Core code (`app/models`, `app/services/download`, `app/services/library`)
has zero knowledge this module exists; the only "aware" places are the
composition root (`app/main.py` constructs+starts `SceneCutterService`,
`app/api/v1/router.py` mounts its router), which the convention explicitly
allows.

Runs a single worker thread (unlike `DownloadEngine`'s worker pool) --
scene detection and ffmpeg splitting are both CPU-bound, and parallelizing
several at once on a desktop-local tool isn't worth the complexity.

## Data model

- `scene_cut_job` -- one row per cut request: `video_id` (FK, nullable) XOR
  `source_path` (nullable), `threshold`/`min_scene_len_sec`/`trim_sec`
  params, `status`, `scene_count`, `output_dir`, `error_message`,
  timestamps. Exactly one of `video_id`/`source_path` is enforced by a
  Pydantic `model_validator`, not a DB constraint (SQLite `CHECK` support is
  limited).
- `scene_cut_result` -- one row per output scene file: `job_id` FK,
  `scene_number`, `start_timecode`, `end_timecode`, `file_path`.

## Output location

- Library video source: `library/<platform>/<channel>/<video_id>/scenes/job_<id>/scene-NNN.mp4`
  -- lands next to the video it came from, per the "artifacts live with
  their video" convention.
- Arbitrary local file source: `library/_local_files/job_<id>/scene-NNN.mp4`
  -- placed under `library_dir` specifically so it's still reachable
  through the existing `/media` static mount and previewable in the
  browser, even though the source file itself lives outside the library.

## Endpoints

```
POST /scene-jobs              {video_id | source_path, threshold, min_scene_len_sec, trim_sec}
GET  /scene-jobs?video_id=     list jobs (optionally scoped to one video)
GET  /scene-jobs/{job_id}      status + scenes (once completed)
```

## Frontend

New Sidebar entry "Scene Cutter" (`/scene-cutter`,
`frontend/src/pages/SceneCutterPage.tsx`): a form to pick a video (live
search against `/videos?search=`, debounced 300ms) or type a local path,
tune threshold/min-scene-length/trim, and submit; below it, a polled list
of past/running jobs, each rendering its scenes as real `<video>` previews
once completed.

## Non-obvious design decision

The output filename padding (`scene-001.mp4` vs `scene-0001.mp4` for
1000+ scenes) is computed with the exact same formula PySceneDetect's own
`split_video_ffmpeg` uses internally
(`max(3, floor(log10(scene_count)) + 1)` digits) rather than a hardcoded
3-digit guess -- otherwise the `scene_cut_result.file_path` rows written to
the DB could silently point at filenames ffmpeg never actually produced for
very high scene counts.

## Verification

Real end-to-end test, not just code review: built a 3-scene test video with
ffmpeg (red/blue/green), ran both source paths (`source_path` and
`video_id`, the latter via a real imported Library video) through the real
API with curl, confirmed jobs reached `completed` with 3 correctly-timed
scenes and that the output `.mp4` files actually exist on disk and are
servable via `/media`. Then drove the real page with Playwright against a
real Vite dev server + real backend: submitted a job through the UI,
confirmed it reached "Hoàn tất — 3 cảnh" with 3 playable scene previews and
zero console errors, and confirmed the failed-job error state renders
correctly too (caught for free from an earlier bad manual test request).
All test data/files removed afterward.
