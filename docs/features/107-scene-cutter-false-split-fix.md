# 107. Scene Cutter: Fix False Splits + Preview Mode

**Commit:** `c4da2c0`

Real user report: cutting a video that was really one continuous scene
came back split into 3.

## Root cause / scope

`SceneCutterService` uses PySceneDetect's `ContentDetector` with two
user-adjustable knobs (`threshold`, `min_scene_len_sec`), both already
exposed in the Scene Cutter UI. The old default `min_scene_len_sec=0.6`
left the detector free to register a scene as short as 0.6s -- a brief
whip-pan, flash, or motion blur within one real continuous shot can spike
the frame-to-frame content difference above `threshold` for under a
second, and the detector had nothing stopping it from firing a spurious
cut there.

## What changed

- `SceneCutterService._merge_short_scenes` (new): a deterministic
  post-detection safety net -- any resulting scene shorter than 1.0s gets
  absorbed into the scene immediately before it (widening its end), the
  same "guaranteed, not dependent on one tunable being perfectly right for
  every video" merge this codebase already uses twice elsewhere
  (`beat_generate.py`'s `_merge_short_beats` for AI-generated beats,
  `caption/ass_writer.py`'s line-wrap budget). The first scene has no
  predecessor and is left alone if it's short, same edge case
  `_merge_short_beats` already accepts.
- Default `min_scene_len_sec` raised from 0.6 to 1.2 (both backend
  `SceneCutJobCreateIn` and the frontend's matching default) -- the first
  line of defense, reducing how often a sub-second false boundary gets
  registered by the detector at all, before the merge safety net even runs.
- Added hint text under the Threshold/Min-scene-length inputs in the UI
  explaining what each does and pointing at "Độ nhạy" (threshold) as the
  knob to raise if a video's real, multi-second content still gets
  over-split -- the merge safety net only catches sub-second spurious
  scenes, not the case where the detector is genuinely too sensitive for a
  specific video's own motion/lighting.

`threshold` itself (46.0) was initially left unchanged -- see the
follow-up below, where the user's own real video proved this wasn't
enough on its own.

## Verification

Backend: `tests/modules/scene_cutter/test_service.py` (new) -- 6 tests
against real `scenedetect.FrameTimecode` instances (no video file/OpenCV
needed for the merge logic itself): a short scene absorbs into its
predecessor, a scene that's long enough on its own is untouched even
immediately after a merge, multiple consecutive short scenes all chain
into the same predecessor, a short opening scene (no predecessor) is left
alone, and the single/empty-list edge cases. `npx tsc -b --noEmit` clean.

Real, non-mocked verification: ran an actual scene-cut job through the
running app's own API against a real local video file, end to end
(detection -> merge -> ffmpeg split -> DB persistence). Confirmed the new
`min_scene_len_sec: 1.2` default was applied and the real result (5
scenes, shortest 4.5s) had no fragment shorter than the floor. Test job
and its output files cleaned up afterward.

## Follow-up: threshold default raised 46 -> 60 (commit `c72c414`)

The user re-tested against their own real video (a fast, handheld
reaction-style clip uploaded via the Scene Cutter's own upload feature) and
still got a bad split -- 11 scenes for what should have been closer to 1-2.
Inspected the real DB rows for that job directly: every one of the 11
scenes was already >=1.2s (1.6s-13.8s), so the merge-short-scenes safety
net above genuinely couldn't have caught it -- this was the detector being
too sensitive for this video's own content, not a sub-second flicker.

Pulled real frames from the video at the detected cut points
(`ffmpeg -ss ... -frames:v 1`) to see what was actually triggering each
cut. Confirmed by eye: some boundaries were a real cut (a different person/
composited reaction shot spliced in around 17.5s); most were the *same*
continuous handheld shot with fast camera movement (the subject bringing a
trimmer up to his face, changing framing) -- exactly the kind of large
frame-to-frame visual change that a plain content-difference detector
can't distinguish from a real cut.

Before changing the default, tested empirically against this same real
video rather than guessing:

| Detector | Setting | Scenes |
|---|---|---|
| ContentDetector | threshold=46 (old default) | 11 |
| ContentDetector | threshold=55 | 5 |
| ContentDetector | threshold=65 | 6 |
| ContentDetector | threshold=75 | 2 |
| ContentDetector | threshold=85 | 0 |
| AdaptiveDetector (`scenedetect`'s own detector, marketed as more robust to camera movement) | adaptive_threshold=3/5/8 | 23 / 23 / 19 |

`AdaptiveDetector` made this specific video meaningfully *worse*, not
better -- ruled out as an alternative. Raised the default `threshold` from
46.0 to 60.0 (`SceneCutJobCreateIn` and the frontend's matching default) --
a real, empirically-informed middle ground for this app's own actual
content, not just PySceneDetect's generic CLI default (27.0). Re-ran the
same real video end to end at the new default: 6 scenes instead of 11, and
critically the whole 40-second continuous handheld portion that had
previously fragmented into 5+ pieces now came back as one single scene.
Test job and output files cleaned up afterward. Still fully
user-adjustable per video via the "Do nhay" field for content that needs a
different balance (the hint text added above already points at it).

## Follow-up 2: Preview mode (detection only, no cut)

The user tried several more of their own real videos at the new default
and still got messy results ("cảnh lộn tùm lum") -- inspected two of their
actual uploaded videos directly (pulled real frames at the detected cut
points with `ffmpeg -ss ... -frames:v 1`) and found the fundamental
problem: different videos in this genre need *opposite* threshold
settings. One was a single continuous handheld shot (needs a high
threshold to avoid false splits from camera movement); the other turned
out to be a compilation of several different people's clips stitched
together (needs a lower threshold, or 60 wrongly merges different people's
segments into one "scene"). Also empirically tried `scenedetect`'s
`HashDetector` and `HistogramDetector` against both real videos as
alternative algorithms -- both produced dramatically more false scenes
(20-28) than `ContentDetector`, ruling them out.

Conclusion: there is no single default that suits every video in this
genre, and no better detector currently available in the library --
per-video tuning via the threshold field is genuinely required. The real
problem was the *workflow*: finding the right threshold required running a
full cut (ffmpeg writing real files) each time just to see if a guess was
right.

Added a Preview mode: `SceneCutterService.preview_scenes()` (new, shares
`_resolve_input_path` -- extracted from `_resolve_paths` -- with the real
job path) runs detection only, no `split_video_ffmpeg`, no `SceneCutJob`
DB row, nothing written to disk. New endpoints `POST /scene-jobs/preview`
(JSON, mirrors `create_scene_job`) and `POST /scene-jobs/preview/upload`
(multipart, mirrors `upload_scene_job`) return `{scene_count, scenes:
[{start_timecode, end_timecode, duration_sec}]}`. Frontend: a "Xem trước"
button next to "Cắt thành cảnh" shows the same scene list inline (with the
threshold/min-scene-length used) without creating a job -- the user can
try several threshold values back to back before committing to a real cut.
Also fixed `upload_scene_job`'s own hardcoded `Form(46.0)`/`Form(0.6)`
defaults, stale since Follow-up 1 changed `SceneCutJobCreateIn`'s real
defaults to 60.0/1.2 (harmless in practice -- the frontend always sends
explicit values -- but wrong for anyone calling the endpoint directly).

### Verification

Backend: new `PreviewScenesTests` (missing-file error path, no DB/OpenCV
needed) alongside the existing `MergeShortScenesTests` -- 7 tests passing.
`npx tsc -b --noEmit` clean.

Real, non-mocked verification: called the actual `POST /scene-jobs/preview`
endpoint against a real video at threshold=70 -- returned in under a
second (vs. several seconds plus file writes for a real cut) with the
correct 3-scene result, and confirmed via direct DB inspection that no
`scene_cut_job` row was created. Then drove the real running app through
Playwright: switched to "Đường dẫn file cục bộ", entered the same file,
set threshold to 70, clicked "Xem trước", and confirmed the exact same
3-scene result rendered inline in the UI with the "chưa cắt file, chỉ dò
thử" label.
