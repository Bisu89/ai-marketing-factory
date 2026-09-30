# 156 — Readable output folder and video names

**Commit:** _uncommitted_

Real user report: every render landed in a bare `job_<id>` folder holding
an identically named `video_hoan_chinh.mp4` (Storyteller:
`episodes/<id>/final.mp4`), so finding one particular video meant opening
folders one by one. Output
folders and final videos are now named after what they contain, with the
id kept in front so they stay unique and sort by creation order.

## What changed

| Where | Before | After |
|---|---|---|
| Video Composer / Factory job folder | `_video_composer/job_12/` | `_video_composer/job_12_<title>/` |
| Final video | `output/video_hoan_chinh.mp4` | `output/job_12_<title>.mp4` |
| Storyteller episode | `episodes/7/final.mp4` | `episodes/7_<title>/7_<title>.mp4` |

`<title>` is the job's own title -- for Factory renders that is
already the project name (`factory_stages.py` passes `plan.project_name`
as the job title).

## Key files

- `backend/app/core/output_naming.py` -- new: `safe_label` (strips
  Windows-forbidden characters, keeps Vietnamese diacritics, max 50 chars),
  `labeled_name`, `find_labeled_dir`/`resolve_labeled_dir`,
  `labeled_video_filename`.
- `backend/app/modules/video_composer/service.py` -- `job_dir()` and the new
  `final_video_path()`; both final-video code paths (classic `_run_job` and
  precomposed `_run_final_composition`) plus their tmp/outro tmp names.
- `backend/app/modules/video_composer/router.py` -- the dub placeholder
  title moved into the service as `DUB_PLACEHOLDER_TITLE`.
- `backend/app/modules/storyteller/service.py`.
- `backend/app/api/v1/endpoints/package_generate.py` -- removed
  `ensure_named_video`/`named_video_filename`.

## Design decisions

- **An existing folder is always reused.** `resolve_labeled_dir` first
  looks for the id's folder already on disk (bare legacy `job_<id>`, or
  `job_<id>_<anything>`), and only builds a new name when there is none.
  This keeps every pre-upgrade job working, and keeps a job's files in one
  folder when its title changes mid-run: Chinese Drama dub jobs save their
  input under the placeholder title `(Đang dịch...)` and only get their real
  title after translation. For those, the folder is labeled after the
  uploaded file's name instead of the placeholder.
- **The final video repeats the `job_<id>_` prefix** instead of being just
  `<title>.mp4`: a user-chosen output folder can be shared by many jobs,
  where the old fixed name made every job overwrite the previous one's
  video, and two projects can share a title.
- **Nothing reads these names back.** Every consumer (packaging, Final QA,
  download/open-folder endpoints) already used the path stored
  on the job row (`output_path`, `output_dir`, `file_path`), so no reader
  needed to learn the new scheme. That also made Task 53's packaging-time
  hard link (`<project name>.mp4` beside `video_hoan_chinh.mp4`) redundant,
  so it was removed rather than left producing a second copy.
- **Existing files are not renamed.** Their absolute paths are stored in the
  DB; only new renders use the new names.
- **Scene Cutter** got the same treatment during this change, but was
  removed entirely right after (see
  [157-remove-unused-features.md](157-remove-unused-features.md)).
- **Not renamed:** `.render/job_<id>/` (internal report/log folders, looked
  up by id only) and the per-project intermediate caches
  (`_audio/project_<id>`, `_motion/...`, etc.) -- none of them hold a
  deliverable video.
