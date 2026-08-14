# 38 — Render Job Hardening: Local Queue, Cancel, Recovery, Retry

**Commit:** _(fill in after commit)_

## What it does

Turns a render into a real persistent local job: non-blocking submission
(`POST /video-compose-jobs/from-composition` now returns as soon as the job
is QUEUED, not after the whole render finishes), cancellation (queued or
running, with the actual owned ffmpeg process terminated), crash recovery
(a job interrupted by an app/PC crash is marked FAILED with a specific
error code, never left RUNNING forever), and explicit retry. No new job
system was built — `VideoComposerService`'s existing queue+worker-thread
(already present since Task 08, the same shape `DownloadEngine` uses) is
extended in place, mirroring `DownloadEngine`'s own pluggable-`Downloader`
and per-job `JobControl` (cancel event) patterns already established in
this codebase.

## What already existed (not rebuilt)

A local FIFO single-worker queue, per-phase status persistence, and
startup recovery of interrupted jobs all already existed
(`VideoComposerService._queue`/`_worker_loop`/`_recover_pending_jobs`,
Tasks 08 & 10). What was missing: RENDER_BEATS ran synchronously inside
the HTTP request (blocking `POST` for the whole beat-render phase — ~17s
in the Task 10 benchmark), there was no cancellation of any kind, and
interrupted jobs were silently re-queued rather than surfaced as failed.

## Job architecture

```
Render Request (POST /video-compose-jobs/from-composition)
      |  preflight only (fast; already existed, Task 10) -- rejects a bad
      |  request immediately, before it's ever queued
      v
VideoComposeJob row (status=queued, composition_request_json stored)
      v
VideoComposerService's existing local queue (FIFO, one worker thread)
      v
_run_job: RENDER_BEATS -> COMPOSE_VIDEO -> BUILD_AUDIO -> BURN_CAPTIONS ->
          VALIDATE_OUTPUT -> COMPLETED/FAILED/CANCELLED
      v
final.mp4 + report.json + render.log
```

**The key architectural move**: RENDER_BEATS (the actual per-beat ffmpeg
motion rendering) moved off the HTTP request thread and onto the worker.
Since `app.modules.video_composer` must never import `app.modules.motion`
or `app.modules.composition` (per `app/modules/README.md`), the worker
can't do that rendering itself — it calls an injected `beat_renderer`
callable (`VideoComposerService.__init__(beat_renderer=...)`), exactly the
same dependency-inversion shape `DownloadEngine(downloader=YtdlpDownloader())`
already uses. The real implementation, `render_beats_for_job`, lives in
`composition_render.py` (the composition root, allowed to import all
three modules) and is wired in at `app/main.py`. The whole original
request (`plan`/`asset_paths`/`narration_asset_paths`/`profile`) is
persisted as `composition_request_json` on the job row so the worker can
rebuild it, and so `retry_job` can resubmit an equivalent request later.

## State machine

```
QUEUED --enqueue-not-yet-started--> CANCELLED   (cancel_job, immediate)
QUEUED --worker picks up--> RENDER_BEATS --...--> VALIDATE_OUTPUT --> COMPLETED
  (any RUNNING phase) --cancel_job--> CANCELLED  (checkpoint/process-kill)
  (any RUNNING phase) --exception--> FAILED
  (any RUNNING phase, app crash)  --startup recovery--> FAILED (RENDER_INTERRUPTED)
```

`status` (fine-grained: `queued`/`rendering_beats`/`merging`/`narrating`/
`subtitling`/`mixing_audio`/`finalizing`/`validating`/`completed`/`failed`/
`cancelled`) remains the persisted source of truth — existing tests, the
progress UI, and recovery all key off it. Two new derived, API-facing
fields (`app.modules.video_composer.models.COARSE_STATUS`/`RENDER_PHASE`,
surfaced via `VideoComposeJobOut.job_status`/`.phase`) give the brief's
exact 5-value (`QUEUED`/`RUNNING`/`COMPLETED`/`FAILED`/`CANCELLED`) and
7-phase (`RENDER_BEATS`.. `VALIDATE_OUTPUT`, PREFLIGHT excluded — it runs
before a job exists) vocabulary without a second status column to keep in
sync. A terminal job (`COMPLETED`/`FAILED`/`CANCELLED`) can never be
re-cancelled or silently mutated — `cancel_job` returns `False` for one,
`retry_job` always creates a new job row instead.

## Recovery

`_recover_pending_jobs` (called from `VideoComposerService.start()`, i.e.
on every app startup) now splits pending jobs in two: a job still
`"queued"` never actually started, so it's safely re-queued exactly as
before. A job in any other non-terminal status was genuinely RUNNING when
the process died — an ffmpeg encode killed mid-write can leave
corrupt/partial intermediates (unlike a resumable HTTP download, which is
why `DownloadEngine`'s equivalent recovery silently re-queues instead), so
these are marked `FAILED` with `error_code=RENDER_INTERRUPTED` and a
failure `report.json`, never silently re-run. **Real, not simulated,
verification**: launched the backend, submitted a real 5-beat render,
waited for it to reach `rendering_beats`, hard-killed the process
(`Popen.kill()`), relaunched, and confirmed the job was recovered exactly
as `FAILED`/`RENDER_INTERRUPTED` — then called retry and watched the new
job render to completion for real. See "Manual verification" below.

## Cancellation

`cancel_job(job_id)`: a `QUEUED` job is cancelled immediately in the DB. A
running job gets an in-memory cancel signal (`threading.Event` per job,
mirroring `DownloadEngine.JobControl` — never persisted, runtime-only
state) plus immediate termination of whatever ffmpeg `Popen` process that
job currently owns (`VideoComposerService._active_processes`, registered/
unregistered around each `render_motion_clip` call via a new
`on_process_start` callback added to `app/modules/motion/renderer.py`).
Only the process a job itself registered is ever touched. Phases after
RENDER_BEATS check the cancel flag at phase boundaries (each phase is a
handful of seconds — see the Task 10 benchmark — so worst-case latency is
bounded without needing every `_run_ffmpeg` call site to track its own
process). **Real verification**: submitted a real render, cancelled it
mid-`RENDER_BEATS`, and the job reached `CANCELLED` in **0.12 seconds** —
proof the live ffmpeg process was actually killed, not waited out.
Scratch files (`scenes/`, `tmp/`) were confirmed deleted; source
assets/library files are never touched. A second render submitted
immediately after completed normally, proving the queue recovers cleanly.

## Changed files

Backend: `app/core/exceptions.py` (+`RenderCancelled`), `app/core/config.py`
(+`min_free_disk_mb`), `app/core/render_errors.py` (+`INSUFFICIENT_DISK_SPACE`,
+`RENDER_INTERRUPTED`, +`rendering_beats` phase mapping), `app/modules/motion/renderer.py`
(`render_motion_clip` now Popen-based with `on_process_start`/`is_cancelled`
hooks), `app/modules/video_composer/models.py` (+`rendering_beats`/`cancelled`
statuses, +`COARSE_STATUS`/`RENDER_PHASE`, +`composition_request_json`,
+`previous_job_id`, +`render_progress_current/total`), `app/modules/video_composer/service.py`
(beat_renderer/event_bus injection, `cancel_job`, `retry_job`,
`set_beat_progress`, per-job log file, rewritten `_recover_pending_jobs`),
`app/modules/video_composer/schemas.py` (+`job_status`/`phase`/`progress_*`/
`previous_job_id`), `app/modules/video_composer/router.py` (+`/cancel`,
+`/retry`), `app/api/v1/endpoints/composition_render.py` (`render_composition`
now only does preflight + enqueue; new `render_beats_for_job` worker hook;
disk-space preflight check), `app/main.py` (wires `beat_renderer`/`event_bus`
into `VideoComposerService`, mirroring `DownloadEngine`'s `Downloader`
injection). Manual `ALTER TABLE` on `data/library.db` for the new columns.

Frontend: `types/videoComposer.ts` (+statuses, +`CoarseJobStatus`/`RenderPhase`,
+progress/job_status fields), `api/videoComposer.ts` (+`cancelVideoComposeJob`,
+`retryVideoComposeJob`), `pages/VideoFactoryPage.tsx`/`.css` (phase checklist
with real beat progress, Cancel button, Fix/Retry buttons, a small "Recent
renders" list reusing the existing `GET /video-compose-jobs`, polling stops
once a job reaches a terminal state), `pages/VideoComposerPage.tsx` (status
label map updated for the 2 new statuses, since it shares the same type).

## Tests

351 backend tests passing (up from 332 at task start): new
`tests/modules/video_composer/test_job_lifecycle.py` (state machine, FIFO/
single-concurrency queue with a fake controllable beat renderer, cancel-
while-running with the real worker thread, crash recovery, retry, plus one
real-ffmpeg cancellation test proving an actual OS process is terminated
in well under its natural render time) and updates to existing
`test_composition_render.py`/`test_golden_sample_render.py` fixtures for
the async beat-rendering handoff.

## Manual verification

Both explicitly required manual scenarios were run for real (not just
unit-tested), as scripted, non-interactive end-to-end runs against a real
backend process — see the "Recovery"/"Cancellation" sections above for
results. Retry-after-recovery was verified as part of the same recovery
run (the retried job rendered to completion with real ffprobe-verified
output). A render submitted immediately after a cancellation also
completed normally, confirming the queue/worker isn't left in a bad state.

## Performance

From the manual runs: queue wait was 0 (single job in flight each time).
5-beat render time ~14.4s (worker-side pipeline), full request-to-QUEUED
response now near-instant (preflight only, well under 100ms) versus
~17s+ before this task. Cancellation latency: 0.12s.

## Cost

External API calls: 0, external cost: $0 for the local-narration
verification renders. A separate sanity render using TTS narration
correctly reported `external_api_calls: 1`, `external_api_cost_estimate: null`.

## Problems

None outstanding. One known, pre-existing limitation carried over from
Task 10 unchanged: local narration and burned captions remain mutually
exclusive (no transcript exists for pre-recorded audio) — irrelevant to
this task's scope.

## Architecture

No Redis/Celery/RabbitMQ/external queue/microservices were introduced. No
second event bus (reused `app.core.events.EventBus`, now also passed to
`VideoComposerService`, publishing `render.job.started`/`.phase_changed`/
`.progress`/`.completed`/`.failed`/`.cancelled`). No second FFmpeg process
manager or render pipeline — `_run_ffmpeg`/`_merge_clips_with_transitions`/
etc. are untouched; only `render_motion_clip` gained optional cancellation
hooks. No module-to-module imports: `video_composer` still never imports
`motion` or `composition`; the only new cross-module knowledge lives in
`composition_render.py` (already the sanctioned composition root) and its
injection into `app/main.py`.

## Next task

Task 12 — Project Templates + One-Click Video Factory Presets.
