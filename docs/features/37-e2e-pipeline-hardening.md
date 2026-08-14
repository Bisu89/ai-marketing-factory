# 37 — End-to-End Pipeline + Cost-Aware Render Profile

**Commit:** _(fill in after commit)_

## What it does

Hardens the already-working Video Factory pipeline (Tasks 02-36) rather
than rebuilding it: adds preflight checks that were missing (background
music/font/ffmpeg-ffprobe/output-dir), a named render profile
(`SOCIAL_VERTICAL`/`PREVIEW`), atomic final output (no `final.mp4` is ever
exposed until validated), real ffprobe-based final validation, and a
`.render/job_<id>/report.json` with per-phase timing and honest external-API
cost accounting. No new orchestrator, no new render API, no new module --
`render_composition()` (`composition_render.py`) + `VideoComposerService`
already were the single entry point; this task extends both in place.

## What already existed (not rebuilt)

Preflight (asset-file existence), a render lifecycle (`queued -> merging ->
narrating -> subtitling -> mixing_audio -> finalizing -> completed/failed`),
per-render timing, and `render_metadata.json` cost tracking (`ai_cost:
0.0`) were all already shipped (Tasks 28, 35). This task widens preflight,
adds one new lifecycle phase (`validating`), and replaces the always-0.0
cost assumption with real accounting.

## Render profile

`app/core/render_profile.py` (new): `SOCIAL_VERTICAL` (1080x1920/30fps)
and `PREVIEW` (720x1280/24fps), both h264/aac/yuv420p. `profile` is a new
field on the render request, validated and recorded on the job
(`render_profile` column) -- it deliberately does **not** overwrite a
Scene's own `output_format`. An earlier version of this change did
override it, which broke several existing tests that intentionally render
at small custom resolutions for speed; `Scene.output_format` remains each
caller's own authoritative per-scene contract, exactly like the rest of
this codebase's "duplicate the pattern, don't force it" convention. The
frontend's existing `OUTPUT_FORMAT` constant is documented as mirroring
`SOCIAL_VERTICAL` and now also sends `profile: "SOCIAL_VERTICAL"`.

## Preflight

`_run_preflight` (`composition_render.py`, replaces the narrower
`_preflight_validate`) now also checks: background music file exists,
narration audio files exist, caption fonts exist, `ffmpeg`/`ffprobe` are on
PATH, and the output directory is writable -- all before any motion
rendering starts. Raises the first problem found using this codebase's
existing exception types (`ValidationError` for "your input is wrong",
`FileOperationError` for "a file/binary/dir isn't there" -- both already
asserted on by the pre-existing test suite), with each message prefixed by
a stable code from the new `app/core/render_errors.py`
(`MISSING_ASSET`, `FFMPEG_NOT_FOUND`, `OUTPUT_DIR_NOT_WRITABLE`, etc.).

## Atomic output + final validation

`_finalize` now writes to `.video_hoan_chinh.tmp.mp4`; only after a new
`VideoComposerService._validate_final_output` (real ffprobe: file exists,
video+audio streams present, duration within 0.5s tolerance of the merged
clips' own duration, resolution/fps match what this job actually targeted,
`h264`/`yuv420p`/`aac`) passes is it atomically renamed to the real
`video_hoan_chinh.mp4`. Validation failure deletes the tmp file and fails
the job with `OUTPUT_VALIDATION_FAILED` -- catches the same class of bug
Task 35 found by hand (wrong pixel format) automatically, on every render,
going forward. New `validating` status between `finalizing` and
`completed`.

Resolution/fps are validated against what the pipeline **actually probed
and targeted for this render** (`clip_paths[0]`), not the named
`RenderProfile` -- the plain upload-based Video Composer flow legitimately
renders whatever resolution its uploaded clips already are, so a hard
profile check there would break real, working functionality.

## Render report + cost accounting

`.render/job_<id>/report.json` (new, under `library_dir`, independent of a
custom output dir) is written on both success and failure:
`status`/`video`/`beats`/`captions`/`external_api_calls`/
`external_api_cost_estimate`/`timing` (`preflight`, `beat_render`,
`composition`, `audio`, `captions`, `validation`, `total`) on success;
`status`/`error_code`/`message`/`failed_phase`/`timing` on failure.
`error_code` is derived from which phase the job was in when it failed
(`render_errors.PHASE_TO_ERROR_CODE`). `preflight_seconds`/
`beat_render_seconds` are timed by the composition-root adapter (both
phases run synchronously in the HTTP request, before the job even exists --
a pre-existing design this task didn't change) and passed through as new
job columns. `VideoComposeJobOut`/`job_to_out` surface all of this.

**Cost accounting changed on purpose**: Task 28 always reported `ai_cost:
0.0`, reasoning that edge_tts is free. This task's own accounting rule is
stricter and more honest: an external network call is 1 call with an
*unknown* cost (`null`), never an invented `$0`, even for a free/unofficial
API -- only `narration_mode="local"` (genuinely zero network calls) reports
`0`/`0`. The pre-existing `render_metadata.json` sidecar (`ai_cost: 0.0`)
is untouched for backward compatibility; the new report is the accurate one.

## Known limitation: local narration and captions are mutually exclusive

Unchanged from Task 36: `narration_mode="local"` forces `burn_subtitles=False`,
since a pre-recorded clip has no word-boundary transcript to caption from.
The brief's example scenario ("local narration + captions burned + $0
cost") is therefore not achievable simultaneously without local
speech-to-text, which is a new AI feature out of this task's "integration
and hardening only" scope. The full end-to-end test and manual benchmark
both use local narration + local music with captions off (the genuine $0
path); captions-with-TTS-narration was already covered by Task 08's tests.

## Tests

332 backend tests passing (up from 302): new `tests/core/test_render_profile.py`,
new `tests/modules/video_composer/test_pipeline_hardening.py`
(`_validate_final_output`, `_write_render_report`, atomic output, debug-mode
intermediate preservation, failure reports -- all against a real,
unmocked ffmpeg pipeline), expanded `ExpandedPreflightChecksTests`/
`RenderProfileWiringTests` and a new `FullLocalEndToEndPipelineTests` in
`test_composition_render.py` (3 beats/2s each, real local narration + music,
real ffmpeg render, real ffprobe verification, `$0` cost, no mocks besides
the DB session).

## Manual benchmark (real render, job 6)

5 beats / 22.5s raw / 20.9s output (4 crossfades x 0.4s), 1080x1920, 30fps,
local images + local motion + local narration + local music, captions off
(see limitation above): `h264`/`yuv420p`/`aac` confirmed via ffprobe,
`external_api_calls: 0`, `external_api_cost_estimate: 0`, no leftover tmp
file, output opened and visually/audio-verified (frame extraction shows the
correct beat color + title overlay; `volumedetect` mean -27.9dB/max -19.1dB,
no clipping). `timing`: preflight 0.01s, beat_render 17.3s, composition
7.4s, audio 0.9s, captions 5.8s, validation 0.08s, total (async job) 14.2s;
full request-to-completion wall clock 31.9s. Output size 0.38MB (solid-color
placeholder images, not representative of real photos). Backend process
CPU/RAM sampled every 750ms during the render stayed modest (~105-146MB
working set, ~1.8s cumulative CPU) -- this reflects the FastAPI process
only; the actual encode load runs in short-lived `ffmpeg.exe` child
processes not captured by this sampling. Frontend Render step verified live
via Playwright against this same saved 5-beat project: Render Summary
correctly shows "Captions: OFF (local narration)", "External API calls: 0",
"Estimated external cost: $0".

## Cost

External API calls: 0. External cost: $0. Local rendering via FFmpeg only.

## Next task

Task 11 -- Production Hardening + Render Queue + Resume/Recovery.
