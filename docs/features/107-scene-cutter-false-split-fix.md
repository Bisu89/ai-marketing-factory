# 107. Scene Cutter: Fix False Splits (1 Scene Cut Into Several)

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

`threshold` itself (46.0) was left unchanged -- already notably more
conservative than PySceneDetect's own CLI default (27.0), and the "right"
value beyond that is genuinely per-video; the new hint text tells the user
which slider to reach for instead.

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
