# 54 — Final QA + Ready-to-Post: Validate the Finished Package

**Commit:** `15e1949`

Adds a new `FINAL_QA` FactoryRun stage (after `PACKAGING`, before
`COMPLETED`): a read-only, deterministic re-verification of the finished
package (final.mp4 + thumbnail.jpg + metadata.json + captions.ass) before
a run is allowed to settle. A FAIL routes the run to `NEEDS_REVIEW` (never
`FAILED`) with `failed_stage="FINAL_QA"` and a `repair_stage` per issue —
mirroring the pre-render Quality Gate's own NEEDS_REVIEW treatment.

## Key pieces

- `app/modules/postqa/` (new, pure `schemas.py`/`analyzer.py` + one
  I/O-owning `renderer.py`): 17 checks (video streams/resolution/fps/
  duration, audio silence/clipping, thumbnail validity/quality, metadata,
  captions validity/timing, beat completeness, dependency staleness,
  package version) — reuses existing check codes (`AUDIO_SILENT`,
  `THUMBNAIL_INVALID`, `PACKAGE_INCOMPLETE`, etc.) where Task 24/26/27
  already established one for the same real-world condition.
- `app/api/v1/endpoints/final_qa.py` (new composition root): builds
  `QAInput` from real ffprobe/volumedetect/Pillow probes plus
  `package_generate.py`/`audio_generate.py`/`caption_generate.py`/
  `motion_generate.py`'s already-resolved artifact paths; persists
  `qa_report.json` next to `final.mp4`.
- `factory_pipeline.py`: `_on_render_job_completed` now runs FINAL_QA
  synchronously after PACKAGING; `continue_run`/`retry_run` and their
  batch equivalents gained `failed_stage == "FINAL_QA"` branches (resume
  via QA re-check, never via the pre-render Quality Gate or a re-render);
  `FactoryRun` gained `qa_status`/`qa_score` (kept separate from the
  Quality Gate's own `quality_status`/`quality_score` — different checks,
  neither should overwrite the other's cached outcome).

## Non-obvious decisions

- **Staleness is mtime-based, not fingerprint-based**: no fingerprint is
  ever recorded at render time (a pre-existing gap noted in Task 26's own
  docs), so `STALE_DEPENDENCY` compares `audio_master.wav`/`captions.ass`
  mtimes against `final.mp4`'s own mtime instead.
- **Score is informational only**: `overall_status` is computed
  independently of `score_from_checks` — a single FAIL always wins
  regardless of score, so a high score can never mask a real problem.
- **`check_metadata` deliberately does not require non-empty hashtags**,
  matching Task 27's own `validate_package`, which already treats an
  empty hashtag list as a complete package — QA must agree with Task 27's
  own standard, not invent a stricter, disagreeing one for the identical
  artifact.

## Real bug found and fixed during this task

`_on_render_job_completed` (and `retry_run`/`retry_batch_failed`'s own
PACKAGING-retry branches) resolved settings via a bare `get_settings()`
call. In production that's a real singleton and always agrees with the
rest of the pipeline; in the test harness it silently returned a
*different* `Settings` instance than the one tests construct, so
FINAL_QA's `captions_ass_path`/`audio_master_path` lookups (which, unlike
Packaging's own paths, depend on `settings.library_dir`) looked in the
wrong directory and reported false FAILs. Fixed by patching
`factory_pipeline.get_settings` in `_FactoryTestCase.setUp()`.

## Tests

67 new: `tests/modules/postqa/test_analyzer.py` (49, pure), `test_renderer.py`
(18, real ffmpeg/ffprobe/Pillow), `tests/api/test_final_qa_stage.py` (16,
full pipeline — pass/fail detection, NEEDS_REVIEW settle, continue/retry,
crash recovery, idempotency, no-mutation, multi-project). Full backend
suite: 1014/1014 passing (one pre-existing Windows tempdir cleanup flake,
confirmed unrelated by isolated rerun).

## Next task

Task 29 — End-to-End Factory Hardening: 20 Videos → Overnight Production
→ Recovery/Resume/Resource Limits.
