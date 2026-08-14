# 34 — Local Motion Renderer with FFmpeg

**Commit:** _(fill in after commit)_

## What it does

Wires a real, single-beat "Preview motion" button on the Video Factory's
Visual step to the local ffmpeg renderer: image + Beat.motion_preset +
duration -> one playable MP4 clip, synchronously, in a few seconds. Also
fixes two real, previously-undetected distortion bugs in that renderer
(below) found while verifying this task's own "no black borders, no
stretching" requirement.

## The renderer already existed

This task's brief assumed a green-field renderer. It doesn't need one:
`app.modules.motion.renderer.render_motion_clip()` already existed, complete
and heavily tested, from several tasks ago
([23](23-local-motion-renderer.md)) -- resolver (`build_motion_plan`,
[21](21-motion-domain-presets.md)) + pure command builder
(`build_filter_graph`/`build_ffmpeg_command`) + I/O orchestrator
(`render_motion_clip`), exactly the shape this task asks for. Bundled
ffmpeg resolution was also already solved (`app/main.py`'s
`_prepend_bundled_ffmpeg_to_path`, which every ffmpeg/ffprobe call in this
app already resolves through via PATH). None of that was rebuilt or
duplicated -- the actual new work was a thin single-beat adapter plus two
bug fixes the task's own acceptance criteria (no black borders, no
distortion) surfaced.

## Two real bugs found and fixed

1. **STATIC letterboxed instead of covering.** The old filter chain used
   `scale=W:H:force_original_aspect_ratio=decrease` + `pad` -- "contain"
   (letterboxed, black bars), not "cover". Fixed to
   `scale=W:H:force_original_aspect_ratio=increase` + `crop=W:H`. Caught by
   this task's own explicit requirement, confirmed visually (a 4:3 source
   into a 9:16 output produced visible black bars before, none after) and
   with a new content-level regression test that samples actual corner
   pixels (dimension-only ffprobe checks can't detect letterboxing -- the
   reported canvas size is W×H either way).
2. **Zoompan presets stretched non-uniformly on aspect-ratio-mismatched
   sources.** `zoompan` crops a window whose aspect ratio always equals its
   *input's* aspect ratio, regardless of zoom level, then scales that
   window to the output size. The old prescale step preserved the
   *source's* aspect ratio, not the *output's* -- so a source with a
   different aspect ratio than the target got stretched on every single
   frame of every non-STATIC preset. Manual testing with a source
   containing a real circle made this obvious: the circle rendered as a
   visibly flattened ellipse. Fixed by cover-cropping the prescale stage to
   the *output's* aspect ratio first (`_PRESCALE_FACTOR` on width/height,
   not a fixed absolute size), so the zoompan crop window's aspect ratio
   always matches the output and scaling is never distorting. Confirmed
   with a new regression test that measures a rendered circle's bounding
   box (must stay ~square) and by re-inspecting extracted frames visually.

## Renderer architecture (unchanged, reused as-is)

```
Beat.motion_preset (6 uppercase values)
        |  .lower()
        v
app.modules.motion.service.build_motion_plan()  -> MotionPlan (9-preset domain)
        v
app.modules.motion.renderer.render_motion_clip() -> MP4
```

The Motion domain (`schemas.py`/`service.py`) still contains zero ffmpeg
code; the renderer still never branches on `preset` (only reads resolved
scale/position/rotation numbers), so all 6 of this task's presets are
covered by the same one pipeline, no per-preset special cases.

## New adapter: single-Beat preview

`backend/app/api/v1/endpoints/beat_preview.py` -- `POST /beats/preview`.
Crosses three modules (asset, beat, motion), so per this codebase's
established "composition root" convention (`composition_render.py`,
`beat_generate.py`), it lives at the HTTP layer, not inside any one
module. There is no server-side Beat store to look up a `beat_id` from (a
BeatPlan lives in `beats.json` + frontend state only --
[31](31-beat-editor-crud-persistence.md)), so -- mirroring
`CompositionRenderRequest`'s own precedent -- the request carries the data
a preview actually needs (`asset_id`, `motion_preset`, `duration`), not an
id to look up. `AssetService.get_image()` ([32](32-asset-library-beat-visual-assignment.md))
resolves and validates the asset; the output is written under
`library_dir/_beat/previews/` and served by the *existing* `/media`
StaticFiles mount (no new file-serving endpoint needed, unlike Asset.path
which can point outside `library_dir`). Synchronous, no job queue --
matches this task's explicit "short preview, sync is fine" allowance.

## Supported motion

`STATIC`, `SLOW_PUSH_IN`, `SLOW_PULL_OUT`, `PAN_LEFT`, `PAN_RIGHT`,
`ZOOM_AND_PAN` -- the same 6 `BeatMotionPreset` values from
[33](33-motion-presets-beat-motion-assignment.md), resolved to one of
Motion's 9 lowercase presets via `.lower()`.

## Preview

Fully connected, real render (not CSS, not mocked): the Visual step's
"Preview motion" button calls `POST /beats/preview`, shows a loading state,
then an actual `<video>` playing the genuine ffmpeg output plus a
`4.0s • 1080×1920`-style caption. Disabled with a tooltip when no asset is
selected. On error, shows a generic "Unable to render preview." + Retry
(the real error, which can include ffmpeg stderr, is logged to the
console/server log only, never shown verbatim). Preview state is scoped
per-beat (`key={beat.id}` on `VisualsEditor`) so switching beats doesn't
leak a stale preview across selections.

## Tests

Backend: `backend/tests/api/test_beat_preview.py` (new, 7 tests -- default
preset, invalid duration/preset rejected, a real render + ffprobe
verification, missing asset, non-image asset rejected).
`backend/tests/modules/motion/test_renderer.py` (+3: the STATIC cover-crop
filter-graph assertion update, a content-level no-black-corners test, and
the circle-distortion regression test). `python -m unittest discover -s
tests` -- **272 tests, all passing** (262 prior + 10 new).

Frontend: no test framework in this repo -- verified manually (below).

## Manual verification

**Standalone 6-preset render** (bypassing the UI, direct Python): a
1600x1200 synthetic source with a grid + a true circle + corner markers,
rendered through all 6 presets at 1080x1920/30fps/4.0s. ffprobe confirmed
exact duration (4.0s), resolution (1080x1920), fps (30/1), codec (h264),
pixel format (yuv420p) for every preset. Extracted first/mid/last frames
and visually inspected STATIC, SLOW_PUSH_IN, PAN_RIGHT, and ZOOM_AND_PAN
(the task's required subset): no black borders on any edge, the circle
stays round (not stretched) at every frame, pan/zoom motion is smooth and
gradual across first->mid->last, no sudden jumps.

**Real UI flow** (Playwright, live dev servers): selected a beat with a
real assigned image asset and `PAN_RIGHT` motion, clicked "Preview
motion" -- button showed a loading state, then a real, playable `<video>`
(`video.duration === 3`, matching the requested duration) with the correct
`4.0s`-style caption appeared. Confirmed the real `POST /beats/preview`
network call (201, with `preview_media_url`/`duration`/`width`/`height`).
Switching to a beat with no asset correctly disabled the button and
cleared the previous beat's leftover preview; returning and re-rendering
worked a second time. Zero console errors throughout.

## Problems

No platform/FFmpeg issues encountered -- the bundled-ffmpeg PATH mechanism
from earlier tasks worked without modification. The two distortion bugs
above were the only real problems, both existing before this task and
both fixed as part of satisfying this task's own explicit requirements.

## Next task

Task 7 -- Beat Preview + Multi-Beat Composition / Concatenation.
