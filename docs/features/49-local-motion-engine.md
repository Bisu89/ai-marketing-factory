# 49 — Local Motion Engine: Beat Visual → Animated Clip → FFmpeg

**Commit:** `2ff11b8`

Adds a new `GENERATING_MOTION` FactoryRun stage (after `GENERATING_VOICE`,
before `QUALITY_CHECK`) that turns each Beat's visual `Asset` into a real,
cached, independently-retryable animated clip:

```
Beat + Asset -> MotionPlan (preset + intensity + focal point) -> FFmpeg -> beat_<id>.mp4
```

No AI image-to-video generation — deterministic FFmpeg Ken-Burns for
images, trim/scale/crop for existing video assets.

## Key pieces

- `app/modules/motion/service.py` refactored: 9 presets are now relative-
  offset templates (`_PresetTemplate`), and `build_motion_plan()` gained
  `intensity` (SUBTLE/MEDIUM/STRONG) and `focal_x`/`focal_y` parameters —
  MEDIUM + center focal is byte-identical to the old hardcoded numbers, so
  no existing project's rendered output changes unless it opts in.
  `select_auto_motion()` is a new, deterministic (no AI call) rule table +
  beat-index rotation for projects with `MotionProjectConfig.auto_rotate`.
- `app/modules/motion/renderer.py` gained `render_video_clip()` (existing
  video Beat assets are now trimmed/scaled/cropped instead of passed
  through untouched) and `probe_clip()`/`validate_clip_output()` (full
  ffprobe duration/resolution/fps/codec validation, not just "file
  exists").
- `app/api/v1/endpoints/motion_generate.py` (new composition root): the
  idempotent per-beat stage function, a content-hash cache keyed by
  asset+preset+intensity+output-format+renderer-version (sidecar
  `motion.meta.json`), and `motion_artifact_for_beat()` — consulted by
  `composition_render.py`'s existing final-render path to reuse a cached
  clip outright instead of re-rendering, and by the Quality Gate to detect
  a stale/missing artifact.
- `Beat.motion_preset` gained `PAN_UP`/`PAN_DOWN`. `MotionProjectConfig`
  gained `auto_rotate`, `intensity`, `short_video_policy`.

## Pipeline ordering: Motion runs after Voice, not before

The brief's own diagram sketched `VISUAL -> MOTION -> VOICE`. Real
verification found a genuine dependency: Voice recomputes each Beat's
`duration` from real, measured narration timing, which would silently
invalidate any Motion clip already rendered against the original,
pre-Voice duration guess. Motion now runs after Voice and reads the final,
Voice-adjusted `beat.duration`.

## Real bug found and fixed: zoompan pan/zoom froze mid-clip

Manual pixel-level verification (a moving gradient image, not a solid
color) found that every pan/zoom preset — at any output fps other than
25 — reached its own endpoint early and then visibly **froze in place**
for the remainder of the clip, sometimes for over half the clip's
duration. Root cause: FFmpeg's `image2` demuxer for a `-loop 1 -i` single
image decodes at a fixed internal rate (~25fps) regardless of any
`-framerate` flag; zoompan's `d`/`on` progression was being computed from
the *caller's requested output fps* (24, 30, or a test fixture's 10-12),
not that real internal rate, so the animation exhausted its `d`-frame
cycle long before the clip actually ended. This was a pre-existing bug
(confirmed present with the original, unmodified preset numbers) —
unrelated to any Task 23 change, just never previously caught by
pixel-level inspection. Fixed by computing zoompan's `d` from a fixed
`_ZOOMPAN_REFERENCE_FPS = 25` constant, independent of the caller's actual
output fps (which the existing trailing `fps=` filter still produces
correctly). Added a real gradient-image regression test
(`test_pan_progresses_smoothly_across_the_whole_clip_not_just_the_start`)
that fails against the old code and passes against the fix.

## Tests

79 new: `tests/modules/motion/test_service.py` (+18 — intensity, focal
point, auto-selection), `tests/modules/motion/test_renderer.py` (+22 —
video-clip rendering, LOOP/FREEZE/REJECT policy, output validation, focal
crop, the zoompan-freeze regression test), `tests/api/test_motion_stage.py`
(16 — image/video motion, cache/idempotency, invalidation, partial-failure
isolation, crash recovery, pipeline integration), plus updates to existing
composition-render/Quality Gate tests for the new video-trim behavior.
Full suite: 800+ passing.

## Manual verification

Live server against an isolated scratch database (never the real
`data/library.db`): a real 4-beat project with 4 distinct motion presets
completed end-to-end (`GENERATING_MOTION` → `GENERATING_VOICE`'s
downstream reuse → `QUALITY_CHECK` READY 99 → `RENDERING` → `COMPLETED`),
producing 4 real, valid, correctly-timed `beat_<id>.mp4` clips. A 5-project
batch completed with FFmpeg process count never exceeding 1 concurrent
process at any sampled moment — no uncontrolled process explosion.

## Problems

Frontend has Motion intensity/auto-rotate controls on
`VideoFactoryPage.tsx` but no per-beat motion preview UI (the existing
`POST /beats/preview` endpoint already covers single-beat preview and
needed no changes). Face/object detection for focal points was explicitly
out of scope (brief section 11/31) — `focal_x`/`focal_y` exist in the
renderer/service layer but nothing currently populates them from Asset
metadata (no such columns exist on `Asset` yet); every call site passes
the default center for now.

## Next task

Task 24 — Audio Composition + Captions: Narration + BGM + Beat-Synced
Subtitles.
