# 36 — Audio Pipeline: Narration + Background Music

**Commit:** _(fill in after commit)_

## What it does

Adds a true **local-first** narration option: each Beat can reference a
pre-recorded local audio clip (`narration_asset_id`) instead of relying on
edge_tts. Music (project-level, already fully built in earlier tasks) is
now selectable through the Asset Library instead of a bare text path. A
render with local narration + local music makes **zero external network
calls** -- not even to edge_tts's free API.

## What already existed

Most of "the audio pipeline" already existed before this task: `_mix_audio`
already did real sidechain ducking, music looping (`-stream_loop -1`),
trimming to video length, and fade in/out (Tasks 08/25 of the original
epic) -- none of that was rebuilt. `app.modules.asset` already supported
`type="audio"` (Task 20). The actual new work was: (1) per-beat local
narration, which genuinely didn't exist (narration was always one
composition-wide TTS script), and (2) two real bugs this task's own
verification surfaced.

## Local-first narration architecture

```
Beat.narration_asset_id (bare Asset.id, optional)
        v
composition_render.py's _resolve_narration():
  no beat has one set  -> ("tts", None)      -- existing edge_tts path, unchanged
  any beat has one set -> ("local", specs)   -- new path
        v
VideoComposerService._build_narration_timeline(specs, ...)
  -> one concatenated audio file: each beat's own clip (silence-padded if
     shorter) or pure silence (no asset for that beat), in order
        v
_mix_audio (UNCHANGED) -- ducks/mixes/fades exactly as it already did
```

`narration_mode`/`beat_narration_specs` are new `VideoComposeJob` columns
(JSON, same pattern as the existing `sfx_cues` column) -- added via a
manual `ALTER TABLE` on the dev DB (no Alembic in this project, matching
the established convention from earlier additive schema changes). Every
caller that predates this task (including the plain upload-based Video
Composer and every existing test) gets `narration_mode="tts"` via the
column default -- **zero behavior change** for anything that doesn't
explicitly opt in.

## Two real bugs found while verifying this task's own scenario

1. **ffmpeg concat path-doubling.** `_build_narration_timeline` wrote
   segment paths into `concat.txt` relative to the process's cwd, but
   ffmpeg's concat demuxer resolves relative `file` entries against the
   *list file's own directory* -- and this app's default `library_dir` is
   itself relative (`./data/library`), so every real render (not the
   always-absolute-tempdir unit tests) hit "No such file or directory" on
   a doubled-up path. Fixed by writing `path.resolve().as_posix()`
   (absolute) into the concat list, matching the same `.resolve()`
   pattern already used elsewhere in this file for ffmpeg filter paths.
   Caught by a real end-to-end Playwright render attempt, not by the unit
   test suite (which only ever used absolute tempdirs) -- a new regression
   test now asserts every concat-list entry is absolute.
2. **Narration/video sync drift.** The narration timeline was built from
   each beat's *raw* duration, but the merged video's actual beat
   boundaries are crossfade-*shortened* (`_merge_clips_with_transitions`'
   own `safe_transition` overlap). By the last beat of a 5-beat/4-transition
   video, that's up to 1.6s of accumulated drift between "where beat 5's
   visuals start" and "where beat 5's narration was scheduled to start."
   Fixed by having `_resolve_narration` compute each beat's timeline
   *share* using the exact same clamped `safe_transition` formula
   `_merge_clips_with_transitions` uses (already duplicated once in this
   file for `_compute_scene_start_times`), so concatenated narration
   durations sum to the real merged-video duration, not the naive sum of
   beat durations. Validation ("narration exceeds Beat duration") still
   compares against each beat's own raw, user-facing duration -- the
   crossfade overlap is a rendering detail, not something a user's
   narration choice should be rejected over.

## Music via the Asset Library

`CompositionPlan.music_path` was already a plain string (no schema
change needed) -- the Audio step's "Background music" field now has a
"Choose Music" button that opens the same `AssetBrowserModal` used for
images and narration (generalized with an `assetType` prop), sets the
path from the selected asset, and shows a real `<audio>` preview. Manually
pasting a path still works unchanged (backward compatible with the
existing text field).

## Changed files

Backend: `app/modules/beat/schemas.py` (+`narration_asset_id`),
`app/modules/composition/schemas.py` (`SceneAudio` +`narration_asset_id`),
`app/modules/video_composer/models.py` (+`narration_mode`,
+`beat_narration_specs`), `app/modules/video_composer/service.py`
(+`_build_narration_timeline`, `_run_job`'s narration-mode branch, the
yuv420p-adjacent concat-path fix), `app/modules/video_composer/schemas.py`
(unchanged this task, see Task 35), `app/modules/asset/router.py`
(`GET /assets/{id}/file` no longer image-only -- audio previews need it
too), `app/api/v1/endpoints/composition_render.py` (`_resolve_narration`,
`_probe_audio_duration`, preflight wiring). Frontend:
`components/AssetBrowserModal.tsx` (+`assetType` prop),
`api/asset.ts`/`api/videoFactory.ts`/`types/videoFactory.ts`/`types/videoComposer.ts`
(narration/music plumbing), `pages/VideoFactoryPage.tsx` (+`.css`) (Audio
step rewritten to master-detail with a `NarrationEditor`, music picker).

## Tests

Backend: 3 new tests on `Beat.narration_asset_id`, 4 on
`SceneAudio.narration_asset_id`, 9 on `_resolve_narration` (mode
selection, missing mapping, missing file, too-long rejection, gap
preservation, and the crossfade-sync-matches-real-video-duration
regression test), 7 on `_build_narration_timeline` (padding, silence,
ordering, gap preservation, absolute-path regression) +
`LocalNarrationRenderIntegrationTests` (this task's own literal scenario:
3 beats/2s each, local narration + looping music, real `final.mp4`,
h264+aac, correct crossfade-adjusted duration, zero edge_tts calls). Asset
router's `get_asset_file` test updated (audio now served, not rejected).
`python -m unittest discover -s tests` -- **302 tests, all passing** (300
prior + net new after the above).

Frontend: no test framework in this repo -- verified manually (below).

## Manual verification

Built the task's own literal 5-beat/23s scenario end-to-end against the
live app: assigned real local narration clips to beats 1/2/4/5 (beat 3
deliberately left with none) and a real music track via the Audio step's
new pickers; confirmed persistence (`GET /beat-plan` showed the correct
`narration_asset_id` per beat, `None` for beat 3). Triggered a real render
via the same API the frontend calls. Result: `h264`/`aac`, 21.4s (23s − 4
crossfades × 0.4s, matching Task 35's own established formula),
`burn_subtitles: false` (correctly skipped -- no transcript exists for
local narration). Verified the actual audio content objectively with
ffmpeg's `volumedetect` at each beat's crossfade-adjusted window: beats
1/2/4/5 read a consistent ~-29.5dB (narration clearly present), beat 3's
window read -50dB (~20dB quieter -- correctly silent/music-only, the gap
did not shift), the final second showed a lower mean volume consistent
with the configured fade-out, and `max_volume` never approached 0dB
anywhere in the file (no clipping). This is the same class of objective,
non-subjective verification the existing ducking test in this codebase
already used (`test_music_ducking_measurably_reduces_music_level_while_narration_plays`).
Two real bugs (above) were found and fixed during this exact verification
pass, then reproduced-fixed by re-running the identical render.

## Cost

The entire manual verification -- Choose Audio/Music, Save, Render,
listen-equivalent volumedetect analysis -- made **zero calls to any paid
or free external API**. `render_metadata.json`'s `ai_cost` is `0.0` for
this and every other Video Factory render (see Task 28); local narration
mode doesn't even touch edge_tts, unlike the TTS fallback path.

## Problems

Both real bugs found (relative-path doubling in ffmpeg's concat demuxer;
narration/video sync drift from ignoring crossfade overlap) are documented
above, fixed, and regression-tested. No other FFmpeg/audio issues
encountered; the existing music ducking/looping/fade infrastructure needed
no changes at all.

## Next task

Task 9 -- Captions + Final Social Video Polish.
