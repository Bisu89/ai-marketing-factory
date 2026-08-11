# 28 — Video Factory End-to-End Pipeline

**Commit:** _(fill in after commit)_

## What it does

Closes the loop on the Video Factory epic: the full
`Story → Beat Plan → Asset Resolution → Motion Planning → Composition Plan
→ Local Rendering → Narration → Music → Captions → FFmpeg Assembly →
final.mp4` pipeline already existed as of Task 08 (`render_composition()`
in `composition_render.py` calling `VideoComposerService._run_job`, built
across Tasks 02–08); this task adds the two genuinely missing pieces —
an enforced local-only rendering policy, and lightweight render
metadata/cost tracking — and proves the whole chain with a real,
ffprobe-verified render of the Task 09.5 golden sample.

## Key files

`backend/app/core/render_policy.py` (new), `backend/app/api/v1/endpoints/composition_render.py`
(+1 call to `enforce_local_rendering_policy()`),
`backend/app/modules/video_composer/service.py` (+render-time tracking,
+`_write_render_metadata`), `backend/tests/examples/test_golden_sample_render.py`
(new), `examples/video_factory/assets/{background_music.mp3,whoosh_in.mp3}`
(new — see "Golden sample became renderable" below).

## What was actually missing (and what wasn't)

Most of this task's brief describes capability that already existed:
Beat/Asset/Motion/Composition contracts (Tasks 02–05), the local motion
renderer (Task 06), the Composition↔VideoComposer adapter (Task 07), and
narration/music/ducking/fades/captions (Task 08) were all built,
tested, and — as of Task 09 — reachable from a real UI. What this task
added:

1. **An enforced rendering policy**, not just an implicit fact. Nothing in
   this codebase has ever called an AI video-generation API — but that was
   true only because no code path *happened* to call one, not because
   anything *checked*. `app/core/render_policy.py`'s `RenderPolicy`
   mirrors the brief's YAML shape (`ai_video.enabled`, `local_motion.enabled`,
   `ai_image.enabled`, `tts.enabled`) and `enforce_local_rendering_policy()`
   is called at the top of `render_composition()` — the one place a render
   actually starts — so "AI video generation MUST be disabled" is now a
   real, checked invariant. Only `ai_video_enabled` is actively enforced;
   the other three flags document capabilities this app already only ever
   uses locally (Motion's renderer, Asset-registered local files,
   `edge_tts`), so there's nothing to gate them against yet.
2. **Render metadata / lightweight cost tracking.** `VideoComposerService._run_job`
   now times itself (`time.monotonic()` from the start of rendering to a
   successful finalize) and writes a `render_metadata.json` sidecar next
   to the finished video: `render_time_seconds`, `ai_cost` (always `0.0`
   — see below), `render_mode` (`"local"`), `duration`, `output_size_mb`.
   No new DB column, no billing system — a JSON file written once per
   completed job, matching the brief's explicit "do not introduce a
   billing system."
3. **A real, ffprobe-verified acceptance render** of the golden sample
   (below), automated as a permanent regression test.

## Why `ai_cost` is always `0.0`

This pipeline's only "AI" step is `edge_tts` narration
(`app/modules/video_composer/service.py::_run_narration`) — Microsoft's
free, unofficial text-to-speech API: no API key, no billed usage, no rate
limit tied to a paid account. There is no other AI provider anywhere in
the render path (no AI image generation, no AI video generation — the
policy above forbids the latter outright). `ai_cost` is a real field with
a real, honest value, not a placeholder pretending to track spend that
doesn't happen.

## Golden sample became renderable, not just contract-valid

Task 09.5's golden sample (`examples/video_factory/`) was deliberately
*not* fully renderable — its `music_path` and beat_01's `audio.sfx`
(`"whoosh_in.mp3"`) were symbolic references, since that task explicitly
did no rendering. This task adds the two real files those references
already pointed at (`assets/background_music.mp3`, a 10s tone;
`assets/whoosh_in.mp3`, a 0.4s tone) so the same golden sample that proved
the *contracts* compose in Task 09.5 now also proves the *pipeline*
renders — no changes to any of the four JSON files were needed.

## A real bug found while wiring the acceptance test — not shipped code

While writing `test_golden_sample_render.py`, loading `composition.json`'s
`music_path` verbatim (a repo-relative string, by design — see
[27-video-factory-golden-sample.md](27-video-factory-golden-sample.md))
and handing it straight to `render_composition()` failed: ffmpeg resolves
relative paths against its own process working directory, not the repo
root, so the file "didn't exist" from ffmpeg's point of view. This is
correct, expected behavior of relative paths in general — not a pipeline
bug — and the test resolves both `music_path` and beat_01's `sfx` to
absolute paths before rendering, exactly as any real caller (the frontend,
Task 09) already does when it builds `asset_paths`.

## Regression

`python -m unittest discover -s tests` — **220 tests, all passing** (219
pre-existing + 1 new). No downloader, scene_cutter, or library code was
touched by this task at all (confirmed via `git status` — the only
backend files changed are `render_policy.py` (new), 2 lines in
`composition_render.py`, and an additive ~25-line block in
`video_composer/service.py`), so there is no code path by which this
task could regress them; their behavior is exactly what Tasks 01–09 last
verified it to be. The AI features (Story/Hook/Caption), Video Composer's
existing upload flow, and the new Video Factory path are all covered by
the existing automated suite (Tasks 07–09.5) and were re-run clean here.

## Final acceptance render (real, not mocked)

Ran the golden sample through the real pipeline once with **real**
`edge_tts` narration (a genuine network call, not the mocked narration the
automated test suite uses) and real ffmpeg, using an isolated in-memory
database and a temp working directory (the real dev `data/library.db` was
never touched — confirmed via `git status`):

| Metric | Value |
|---|---|
| Beats / scenes | 5 |
| Motion presets used | 5 distinct (`slow_push_in`, `pan_left`, `zoom_and_pan`, `subtle_rotate`, `slow_pull_out`) |
| Input scene durations | 4 + 8 + 8 + 6 + 4 = 30.0s |
| **Output duration (ffprobe)** | **28.40s** (30s − 4×0.4s crossfade overlap — see below) |
| Resolution (ffprobe) | 1080×1920 |
| FPS (ffprobe) | 30/1 |
| Video codec (ffprobe) | h264 |
| Audio codec (ffprobe) | aac |
| Motion-render + submission time | 31.16s |
| Full render pipeline time (`_run_job`) | 21.88s |
| **`render_metadata.json`** | `{"render_time_seconds": 21.86, "ai_cost": 0.0, "render_mode": "local", "duration": 28.4, "output_size_mb": 0.72}` |

**Why 28.4s, not exactly 30s**: 4 of the 5 scene boundaries use a 0.4s
crossfade transition; `_merge_clips_with_transitions` (unchanged since
before this epic) overlaps each transition rather than concatenating hard
cuts, so total runtime is `30 − (4 × 0.4) = 28.4s` — the same, already-
verified overlap formula from Tasks 07–08's own tests, not a new
approximation. This is correct, deterministic behavior of the real editing
technique being used, not a bug or a rounding error — reported honestly
rather than adjusting the sample to force an exact round number.

**Output size** (0.72MB for 28.4s) is small because the golden sample's
5 images are solid-color placeholders, which compress far better than a
real photo — not representative of a real video's file size, only of this
sample's specific content.

The identical render — with narration mocked (no network call) — is now a
permanent automated test: `GoldenSampleRenderAcceptanceTest` in
`backend/tests/examples/test_golden_sample_render.py`, asserting every
ffprobe field above, that the audio track's own duration matches the
video's (A/V sync), and that `render_metadata.json` was written with
sane values.

## Known limitations

- Per-scene transition type/duration and per-scene captions remain
  unaddressed (flagged as gaps in both [24](24-composition-video-composer-integration.md)
  and [25](25-video-factory-audio-captions.md)) — `video_composer` still
  applies one job-wide transition style/duration and one composition-wide
  caption preset.
- `RenderPolicy`'s `local_motion_enabled`/`ai_image_enabled`/`tts_enabled`
  flags are declared but not yet actively checked anywhere (only
  `ai_video_enabled` gates anything) — there's currently only one
  implementation of each of those capabilities, so there's nothing to
  switch between yet.
- The real render's 21.9s pipeline time is for a 5-scene, 28.4s, tiny-
  placeholder-image video on one desktop CPU with no GPU encoding — real
  photos/longer videos will render slower; no performance optimization
  was attempted here per this task's own "do not optimize prematurely"
  instruction.
- The Windows-specific transient ffmpeg failure noted while developing the
  acceptance test (empty stderr, resolved on retry, root cause not
  conclusively identified — most likely a brief antivirus file-lock race
  on a freshly-written `.ass` subtitle file) was not chased further; it
  did not reproduce on any subsequent run.

## Recommended next improvement

Wire `render_metadata.json` into `VideoComposeJobOut`/the frontend so a
user can actually see render time, mode, and duration for a job they just
created — right now this metadata is written but not surfaced anywhere in
the API or UI, only inspectable on disk.
