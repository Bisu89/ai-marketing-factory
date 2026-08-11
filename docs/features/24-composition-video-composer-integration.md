# 24 — Composition ↔ Video Composer Integration

**Commit:** _(fill in after commit)_

## What it does

Lets a `CompositionPlan` (see [22-composition-contract.md](22-composition-contract.md))
with image-backed scenes become a real, finished video: `POST /api/v1/video-compose-jobs/from-composition`
renders each image `Scene` into a clip via the local motion renderer
([23-local-motion-renderer.md](23-local-motion-renderer.md)), passes
already-video scenes straight through, and hands the ordered clip list to
`video_composer`'s **existing, unmodified** merge/narrate/subtitle/mix/
finalize pipeline. Response shape is `video_composer`'s existing
`VideoComposeJobOut` — the result is a completely ordinary `VideoComposeJob`,
pollable through the existing `GET /video-compose-jobs/{id}`.

## Key files

`backend/app/api/v1/endpoints/composition_render.py` (new — the adapter:
`render_composition`, `_scene_motion_to_motion_plan`, `_is_image_path`,
`_derive_transition_duration`, and the thin HTTP wrapper), one new method
`VideoComposerService.save_clip_paths` in
`backend/app/modules/video_composer/service.py`, two lines in
`backend/app/api/v1/router.py`. `backend/tests/api/test_composition_render.py`.

## Architecture: where the adapter lives, and why

Per `app/modules/README.md`, no module may import another — `video_composer`
must never import `motion`/`asset`/`beat`, and (established by
[19](19-beat-domain-contract.md)/[21](21-motion-domain-presets.md)/[22](22-composition-contract.md))
`composition`/`motion` must never import `video_composer` either. But
*something* has to call the motion renderer for image scenes and then call
`video_composer`'s job API — that's exactly the "adapter boundary" this
task asked for.

`app/api/v1/endpoints/*` is core HTTP-layer infrastructure, not a module
under `app/modules/` — the same "composition root" territory
`app/api/v1/router.py` already occupies (it already imports every single
module's router to mount it). `composition_render.py` is a natural
extension of that same, already-sanctioned exception: it's the *only* file
in this codebase that imports `app.modules.composition`, `app.modules.motion`,
and `app.modules.video_composer` together. None of those three modules know
this file exists.

`video_composer`'s own change is the smallest one that makes this possible:
one new method, `save_clip_paths(job_id, paths: list[Path])`, that registers
already-on-disk files as a job's ordered clips without copying them — unlike
`save_input_clips`, which exists specifically for browser multipart uploads
that must be copied to disk first. `create_job`/`save_input_clips`/`enqueue`/
`_run_job` and everything inside it (merge, narrate, subtitle, mix,
finalize) are **completely unchanged**.

## Data flow

```text
POST /video-compose-jobs/from-composition
  { plan: CompositionPlan, asset_paths: {source_asset_id: file_path}, title, output_dir? }
      │
      ▼
render_composition()                              [composition_render.py]
  ├─ service.create_job(...)                       [video_composer, unchanged]
  ├─ for each Scene (in order):
  │     resolve asset_paths[scene.source_asset_id]
  │     if image  → _scene_motion_to_motion_plan(scene.motion, scene.duration)
  │                 render_motion_clip(...)         [motion renderer, Task 06, unchanged]
  │                 → job_dir/scenes/<scene_id>.mp4
  │     if video  → used as-is (no re-encode)
  ├─ service.save_clip_paths(job_id, ordered_clips) [video_composer, NEW]
  └─ service.enqueue(job_id)
      │
      ▼
_run_job()  -- 100% unchanged: merge-with-transitions → narrate → subtitle
               → mix audio → finalize                [video_composer, unchanged]
```

## What is *not* wired through (deliberate, documented scope boundary)

`CompositionPlan`/`Scene` carry more structure than `video_composer`'s
existing contract can express, and "do NOT rewrite the existing composer"
means these are consciously **not** implemented, not overlooked:

- **Per-scene transition type/duration.** `video_composer` only supports
  one uniform `transition_duration` (and a fixed `slideleft` style) for an
  entire job. `_derive_transition_duration()` averages the
  `SceneTransition.duration` of scenes that actually participate in a
  transition (`order > 1`) into one job-wide value; `SceneTransition.type`
  is not honored at all — every merge still uses `video_composer`'s
  existing xfade style regardless of what a Scene requests.
- **Per-scene captions.** `SceneCaption.text`/`.preset` are not read.
  `video_composer`'s existing subtitles are auto-generated from the
  narration audio's own word-boundary timestamps (see
  [11-video-composer.md](11-video-composer.md)) — a fundamentally different
  mechanism than pre-supplied per-scene caption text, and reconciling the
  two would mean rewriting subtitle generation, not extending it.
  **Update ([25-video-factory-audio-captions.md](25-video-factory-audio-captions.md)):**
  a single, *composition-wide* `CompositionPlan.caption_preset` now selects
  one of 5 caption styles for the auto-generated captions — still not
  per-scene, but no longer fixed to one hardcoded style either.
- **Per-scene audio/SFX.** `SceneAudio.sfx` is not read. `video_composer`'s
  existing audio mixing supports one global background-music track, not
  per-scene sound-effect cues layered at specific timestamps.
  **Update ([25-video-factory-audio-captions.md](25-video-factory-audio-captions.md)):**
  `SceneAudio.sfx` *is* now read — `_build_sfx_cues()` turns every scene
  with a non-null `sfx` into a timed cue mixed into the final audio at that
  scene's approximate start offset. Music ducking, narration volume, and
  fade in/out were also added in that task; per-scene transition type/
  duration remains the one gap neither task addressed.
- **Asset resolution.** The endpoint takes `asset_paths` (a plain
  `{source_asset_id: file_path}` mapping) as part of the request rather
  than querying `app.modules.asset` itself — this task is scoped to the
  motion↔composer integration, not an Asset-module integration; resolving
  `source_asset_id` to a real path is left to the caller.

## Verification

Manually confirmed the app boots with the new route registered
(`/api/v1/video-compose-jobs/from-composition`) and that neither
`video_composer`'s nor `composition`'s/`motion`'s own files gained any new
imports (`grep` over each module's imports — unchanged except the one new
method in `video_composer/service.py`).

`python -m unittest discover -s tests` — 153 tests total (16 new, all
against real ffmpeg, auto-skipped if unavailable): an **existing-composer
regression test** (real color-source video clips through the unchanged
upload path, still completes); **CompositionPlan integration tests**
(2-scene and 3-scene plans render real motion clips and complete, clips
saved in correct order, a video-sourced Scene is used without re-rendering,
final duration matches the exact overlap formula
`_merge_clips_with_transitions` itself uses); **failure-surfacing tests**
(a corrupt image raises `FileOperationError` synchronously before any job
is enqueued; a corrupt "video" file reaches the merge stage and the
existing, unmodified `_run_job` marks the job `failed` with a real
`error_message`, proven through the new path exactly as it already works
for uploads); and pure unit tests for the adapter's own helpers
(`_is_image_path`, `_derive_transition_duration`, `_scene_motion_to_motion_plan`,
including its preset-name fallback). All pass in ~13s; the 137 pre-existing
tests (Beat + Asset + Motion + Composition) are unaffected.

TTS narration (`edge_tts`, a real cloud call) is the one piece of
`_run_job` that could not run in an automated, offline test — every
integration test patches `VideoComposerService._run_narration` to
synthesize a short *local* silent track via ffmpeg instead (with
plausible word timestamps), leaving merge/subtitle/mix/finalize running
for real, unmodified, against real files.
