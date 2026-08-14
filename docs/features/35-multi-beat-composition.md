# 35 — Multi-Beat Composition + Final Local Render

**Commit:** _(fill in after commit)_

## What it does

Renders a whole BeatPlan (not just one beat) into a single `final.mp4`:
each Beat's image + motion is rendered via Task 34's local renderer, the
resulting clips are concatenated in `Beat.order` with crossfade
transitions, and the result is validated and returned. Connects the
Render step's "Render Video" button to a real end-to-end render, alongside
the existing single-beat "Preview motion" from Task 34.

## The pipeline already existed

Like several tasks before it, this one assumed a green-field composer.
`app.modules.video_composer` + the `composition_render.py` adapter already
did almost exactly this (built in Tasks 24/25/28 of the original epic):
resolve each Scene's asset, render image scenes via the motion renderer,
hand the ordered clip list to `video_composer`'s existing, unmodified
merge/narrate/subtitle/mix/finalize pipeline. The Render step's "Render
Video" button was already calling this. So the real work here wasn't
building a composer -- it was closing three concrete gaps this task's own
acceptance criteria exposed.

## Three real gaps found and fixed

1. **No preflight -- a missing asset on beat 3 wasted work rendering beats
   1-2 first.** `render_composition()`'s per-scene loop discovered a
   missing/unresolvable asset only when it got to that scene, after
   already running real ffmpeg renders for every earlier one. Added
   `_preflight_validate()`, called before any job is even created,
   checking every scene's asset resolves to an existing file up front --
   `"Beat 3 (scene 'scene_03') has no visual asset assigned."` now fails
   immediately, matching this task's own explicit "do not start rendering
   all previous beats only to discover this halfway through" instruction.
   Covered by two new tests proving zero renders happen when a later
   scene's asset is missing/deleted.
2. **Final output was yuv444p, not yuv420p.** `VideoComposerService._finalize`
   (the last encode step, burning in the title/subtitles) never passed
   `-pix_fmt yuv420p` -- libx264 just kept whatever the filter chain
   produced, which measured as yuv444p on real synthetic test sources.
   Nothing had ever asserted the *final* output's pixel format before (the
   golden sample test only checked width/height/fps/codec). This affects
   every `video_composer` job, not just Video Factory ones -- a real,
   previously-invisible bug, not something introduced by this task. Fixed
   with one added flag; confirmed via a new test that inspects the actual
   final merged output.
3. **Render results (duration/resolution/fps/render time/size) were
   written to `render_metadata.json` but never reachable from the API.**
   Flagged as a known gap in Task 10's own doc. `VideoComposeJobOut` now
   reads that sidecar (`_read_render_metadata`, degrading to `null` fields
   if missing/corrupt/pre-Task-34 -- never an error) and exposes
   `render_duration_sec`/`render_width`/`render_height`/`render_fps`/
   `render_time_seconds`/`output_size_mb`. `_write_render_metadata` itself
   also gained `width`/`height`/`fps`/`clip_count` (previously only
   `render_time_seconds`/`ai_cost`/`render_mode`/`duration`/`output_size_mb`).

## Architecture (unchanged, reused as-is)

```
BeatPlan (frontend) -> CompositionPlan/Scene (buildCompositionPlan, unchanged since Task 4)
        v
composition_render.py: preflight -> render each image Scene via
app.modules.motion.renderer (Task 34) -> ordered clip list
        v
VideoComposerService.save_clip_paths() + enqueue() -> EXISTING,
UNMODIFIED merge (crossfade) / narrate / subtitle / mix / finalize pipeline
        v
final.mp4, served via the existing /media mount
```

Deterministic ordering was already correct (`plan.ordered_scenes()` sorts
by `Scene.order`, itself always derived from `Beat.order`/array position on
the frontend -- never filename or creation time). No new abstraction, no
second composer, no module-to-module import introduced (the adapter still
only lives at the HTTP layer, per the established composition-root
convention).

## Rendering

5-beat manual verification (real assets, real durations 4+5+4+6+4=23s):

| Metric | Value |
|---|---|
| Beat count | 5 |
| Requested total duration | 23.0s |
| Actual output duration (ffprobe) | 21.4s (23s − 4×0.4s crossfade overlap -- expected, same formula as Tasks 10/28) |
| Resolution | 1080×1920 |
| FPS | 30 |
| Video codec | h264 |
| Pixel format | **yuv420p** (confirms the fix) |
| Audio codec | aac (narration -- beats had narration text, included via the existing, unrelated audio pipeline) |
| Full render time | ~32s (5 real motion renders + merge + narrate + finalize) |

## Frontend

Render step (Step 5) now shows a proper "Render summary" (Beats / Duration /
Resolution / Motion: Local / Audio / Assets assigned -- Audio is computed
honestly from whether any beat has narration text and whether music is
set, not a hardcoded "None", since this app's existing audio pipeline
already runs whenever narration text is present). Render progress shows
real backend phase labels (Merging clips -> Generating narration ->
Finalizing -> Completed) via the existing job status enum -- no fake
percentage. On completion: real `<video>` playback, a
`{duration}s • {width}×{height}` caption sourced from the newly-exposed
render metadata, and "Open Folder" (reusing `video_composer`'s existing
`POST /video-compose-jobs/{id}/open-folder`, unchanged) + "Render Again"
(resets local job state) buttons. Single-beat "Preview motion" (Task 34)
is untouched and still works alongside the new Render flow -- both call
the same `app.modules.motion.renderer.render_motion_clip`.

## Tests

Backend: 7 new tests -- 2 preflight tests (missing asset-id mapping,
missing file on disk, both proving zero clips rendered via a mocked
`render_motion_clip`), 1 new 3-beat/2-second visual-order concatenation
test (samples actual pixel colors from the final merged output at each
beat's midpoint, not just clip file paths -- catches ordering bugs the
existing filename-based test couldn't), 4 new `job_to_out` tests (metadata
surfaced, missing/corrupt sidecar degrades gracefully, no-output-yet
degrades gracefully), plus updated assertions in the golden sample test
for the new metadata fields. `python -m unittest discover -s tests` --
**279 tests, all passing** (272 prior + 7 new).

Frontend: no test framework in this repo -- verified manually (below).

## Manual verification

Full real-browser Playwright run of the task's exact 5-beat scenario
(SLOW_PUSH_IN/4s, PAN_RIGHT/5s, SLOW_PULL_OUT/4s, ZOOM_AND_PAN/6s,
STATIC/4s, five distinctly-colored real images). Beat previews (3 of 5
spot-checked) all produced real playable clips with correct
duration/resolution. Save succeeded. Render summary showed the exact
expected values (Beats 5, Duration 23.0s, Resolution 1080×1920, Motion
Local). Render completed in ~32s through real phase transitions. Final
video confirmed via ffprobe: yuv420p, h264, 1080×1920, 21.4s (correct
crossfade-adjusted duration). **Beat order visually confirmed** by
extracting frames at 5 timestamps inside each beat's window: red → green →
blue → yellow → purple, exactly matching beat 1-5 order, with no black
borders and no stretching at any point. Open Folder returned 204 with no
error; Render Again button present and functional.

## Problems

No FFmpeg/platform issues. The two real bugs found (missing preflight,
yuv444p output) were both pre-existing conditions this task's own
acceptance criteria happened to surface, not new issues introduced here --
both are now fixed and regression-tested.

## Next task

Task 8 -- Audio Pipeline: Narration + Background Music.
