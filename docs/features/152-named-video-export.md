# 152 — Final video also saved under the project's own name

**Commit:** `3706364`

Every render's output folder held an identically named `video_hoan_chinh.mp4`,
so episodes copied out of the app were indistinguishable (real user report,
Biblical Figures Ep1 Short). The Package stage now also exposes the final video
as `<project name>.mp4` beside it (`ensure_named_video` in
`backend/app/api/v1/endpoints/package_generate.py`).

- The canonical `video_hoan_chinh.mp4` is kept — `metadata.json`, Final QA
  (`postqa/analyzer.py`) and publishing all reference that exact name.
- Hard link (no extra disk), falling back to `copy2`; Windows-unsafe characters
  stripped. A re-render replaces the canonical file (new inode), so a stale link
  is detected and recreated. Best-effort: never fails packaging.
- Verified on project 104: named file appeared after `regenerate-package`,
  Final QA still PASS 100.
