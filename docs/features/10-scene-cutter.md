# 10 — Scene Cutter (automatic scene-detection video splitting)

**Commits:** `ca44c91` (initial), `bfb8399` (upload + custom output folder +
random filenames), `75a4de7` "Add native folder-picker button to Scene
Cutter's output folder field" (follow-ups).

## What it does

Lets a user cut a video into per-scene clips from the web UI, using
PySceneDetect (content-aware cut detection) + ffmpeg (actual splitting),
without leaving the app or touching a terminal. Source is one of:

- an existing Library video,
- a local file path typed in, or
- a video file uploaded straight from the browser,

and the user can optionally pick a custom destination folder for the cut
scenes (default: next to the source video). Runs as a background job
(`queued` → `analyzing` → `splitting` → `completed`/`failed`) so a
multi-minute video doesn't block the request or the UI; the frontend polls
job status every 2s, same pattern as the History page's download polling.

This wraps the same detection/splitting logic already written as the
standalone `tools/cat_canh.py` script (an interactive-menu CLI tool added
earlier the same day), now exposed as a real in-app feature per the user's
follow-up requests.

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
  params, `requested_output_dir` (nullable -- the user's custom destination
  folder, if given), `status`, `scene_count`, `output_dir` (the actual
  folder used, set once the job reaches `splitting`), `error_message`,
  timestamps. Exactly one of `video_id`/`source_path` is enforced by a
  Pydantic `model_validator`, not a DB constraint (SQLite `CHECK` support is
  limited).
- `scene_cut_result` -- one row per output scene file: `job_id` FK,
  `scene_number`, `start_timecode`, `end_timecode`, `file_path`.

No Alembic in this project yet (see
[05-database-normalization.md](05-database-normalization.md)), so
`requested_output_dir` was added to the already-existing dev table with a
plain `ALTER TABLE ... ADD COLUMN` rather than a migration script.

## Output location

- Custom folder requested: whatever absolute path the user typed, created
  if missing. Scenes there won't have a `media_url` (null) unless that path
  happens to be inside `library_dir` -- browser preview needs the `/media`
  static mount, but the files are still on disk and reachable via "Mở thư
  mục" regardless.
- Library video source, no custom folder: `library/<platform>/<channel>/<video_id>/scenes/job_<id>/`
  -- lands next to the video it came from, per the "artifacts live with
  their video" convention.
- Local-path or uploaded source, no custom folder: `library/_local_files/job_<id>/`
  -- placed under `library_dir` specifically so it's still reachable
  through the existing `/media` static mount and previewable in the
  browser, even though the source file itself may live outside the library.
- Uploaded files themselves are staged at `library/_uploads/<random>.mp4`
  before cutting (kept, not deleted after -- same "everything for one video
  stays together" spirit as the rest of the library).

Scene filenames are random (`<uuid4-hex>.mp4`), not `scene-001.mp4` --
order is already captured by `scene_number`/`start_timecode`/`end_timecode`
on `scene_cut_result`, so the filename itself doesn't need to encode it.

## Endpoints

```
POST /scene-jobs                {video_id | source_path, threshold, min_scene_len_sec, trim_sec, output_dir?}
POST /scene-jobs/upload         multipart: file, threshold, min_scene_len_sec, trim_sec, output_dir?
GET  /scene-jobs?video_id=      list jobs (optionally scoped to one video)
GET  /scene-jobs/{job_id}       status + scenes (once completed)
POST /scene-jobs/{job_id}/open-folder   opens job.output_dir in the OS file explorer
POST /scene-jobs/pick-folder            opens a native folder-picker dialog, returns {path}
```

## Frontend

Sidebar entry "Scene Cutter" (`/scene-cutter`,
`frontend/src/pages/SceneCutterPage.tsx`): three source tabs (pick a
Library video via live search, upload a file -- either via the file dialog
or by dragging it in from Explorer -- or type a local path), an
optional output-folder field (typed manually, or filled in by clicking
"Chọn thư mục..." which calls `pick-folder`), threshold/min-scene-length/
trim inputs, and a submit button; below it, a polled list of past/running
jobs, each rendering its scenes as real `<video>` previews once completed
(or a folder icon placeholder when the scene isn't under `library_dir` and
so has no browser-servable `media_url`), plus a "Mở thư mục" button once
done.

## Non-obvious design decisions

- **Random filenames via a custom `formatter` callback.** PySceneDetect's
  `split_video_ffmpeg` accepts a `formatter(video_metadata, scene_metadata) -> str`
  callback instead of its default `$SCENE_NUMBER` template. The service
  generates the random names up front (before calling ffmpeg) and has the
  formatter just look them up by scene index -- so the exact same names used
  by ffmpeg are also what gets written to `scene_cut_result.file_path`,
  with no risk of the DB and disk disagreeing.
- **Folder picker runs server-side, not in the browser.** A browser's File
  System Access API (`showDirectoryPicker()`) deliberately never exposes an
  absolute filesystem path back to JS, for security reasons -- there's no
  way to get a real path the backend could use for ffmpeg output from that
  API. `POST /scene-jobs/pick-folder` instead pops a native `tkinter`
  directory dialog *on the backend process* and returns the chosen path as
  a string. This only works because this is a desktop-local app where the
  backend and the browser are on the same machine and the same user is
  sitting at both -- it would make no sense for a hosted web app. Windows-only
  for now (raises a clear error otherwise), matching the existing
  `os.startfile`-based open-folder endpoints elsewhere in this app, which
  are similarly Windows-only.
- **A custom `output_dir` is used exactly as given, never nested under a
  `job_<id>/` subfolder** (unlike the two default locations, which are
  nested for collision-avoidance across jobs run against the same video or
  the same default `_local_files` bucket). Once a user has explicitly
  chosen "put my cut scenes here," adding an extra unrequested subfolder
  layer would be surprising; random scene filenames already make
  cross-job collisions inside that folder essentially impossible.

## Verification

Real end-to-end test, not just code review, for both the initial version
and this follow-up:

- Built a 3-scene test video with ffmpeg (red/blue/green), exercised all
  three source modes (`source_path`, `video_id` via a real imported Library
  video, and multipart `upload`) through the real API with curl, plus a
  custom `output_dir` outside `library_dir` -- confirmed jobs reached
  `completed` with correctly-timed scenes, random filenames matching
  between DB and disk, `media_url` correctly null for out-of-library
  output, and the `open-folder` endpoint returning 204.
- Drove the real page with Playwright against a real Vite dev server + real
  backend: uploaded a file through the UI with a custom output folder,
  confirmed "Hoàn tất — 3 cảnh", clicked "Mở thư mục" without error, and
  confirmed zero console errors.
- While testing, discovered the user was independently exercising the same
  feature live, in their own browser, against the same dev database, with
  real uploaded videos (jobs with real multi-scene content unrelated to any
  test fixture) -- confirmed the feature holds up under genuine concurrent
  use. Cleanup afterward specifically targeted only the job IDs and files
  this testing session created (matched by known source paths/hashes)
  rather than clearing the table, to avoid touching the user's own live
  data.
- The `pick-folder` dialog itself was verified by code review + route
  registration + confirming the button renders, not by actually clicking it
  in an automated test -- it opens a real native OS window on whatever
  machine the backend runs on, which would have popped up unprompted and
  blocked waiting for a human to interact with it. Manual click-test still
  needed by an actual user.
- Also hit an unrelated environment hiccup mid-session: the running
  `--reload` dev server stopped responding to any request (health check
  included). Root cause wasn't pinned down for certain -- restarted the
  process rather than debugging a black-box hang further; no data was lost
  since all state lives in SQLite, committed per-request.
