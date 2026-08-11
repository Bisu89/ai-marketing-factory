# 23 — Local Motion Renderer

**Commit:** _(fill in after commit)_

## What it does

The first real rendering engine for the Video Factory: turns one still
image + a `MotionPlan` (see [21-motion-domain-presets.md](21-motion-domain-presets.md))
into a silent H.264 MP4 clip via a local ffmpeg Ken-Burns pipeline
(scale/pan/zoom/rotate) — no AI video generation, no cloud service. Lives
at `backend/app/modules/motion/renderer.py`, alongside (not inside)
`schemas.py`/`service.py`, since `service.py`'s own docstring explicitly
says it contains no rendering code — this file is exactly the "future
rendering layer" that docstring, and [22-composition-contract.md](22-composition-contract.md),
both pointed at without building.

The renderer is **preset-agnostic**: it never branches on `MotionPlan.preset`.
It only reads the resolved numeric fields (scale/position/rotation/easing),
so one ffmpeg pipeline covers all 9 presets — and any future preset —
without nine hand-written special cases.

## Key files

`backend/app/modules/motion/renderer.py` (`build_filter_graph`,
`build_ffmpeg_command` — pure, no I/O — and `render_motion_clip`, which
validates, probes, and executes), `backend/tests/modules/motion/test_renderer.py`.

## The ffmpeg pipeline

1. **Pre-scale** the source image to a large fixed width (`8000px`, aspect
   preserved) before any zoom/pan. zoompan crops at integer pixel offsets
   of its *input* frame, so operating directly on a modestly-sized source
   produces visibly jittery motion — a large pre-scale gives it enough
   sub-output-pixel precision to look smooth. Standard, widely-documented
   zoompan technique, not specific to this app.
2. **`zoompan`** (skipped entirely for the `static` preset — see below):
   `z`/`x`/`y` are ffmpeg expression strings evaluated once per output
   frame, not precomputed in Python. `z` linearly interpolates
   `scale.start` → `scale.end` over an eased progress fraction
   `on/(frame_count-1)` (`on` = zoompan's own output-frame counter); `x`/`y`
   generalize the standard fixed-center Ken-Burns recipe
   (`x='iw/2-(iw/zoom/2)'`) to a time-varying focus point:
   `x = iw*cx(t) - (iw/zoom/2)`, where `cx(t)` is the same eased
   interpolation applied to `position.x_start`/`x_end`. `frame_count =
   round(duration * fps)` is also zoompan's own `d=` parameter.
3. **`rotate`** (only added when `rotation.start != rotation.end != 0` —
   the common case across 8 of 9 presets skips this filter entirely):
   ffmpeg's `rotate` filter uses `t` (seconds elapsed), a *different*
   timeline variable than zoompan's `on` — the same easing function is
   reapplied to `t/duration` and converted degrees→radians
   (`angle*PI/180`) since `rotate` expects radians. Rotating a same-size
   frame in place can reveal its corners; filled with `fillcolor=black`
   rather than computing dynamic zoom compensation for that — an accepted
   simplification for genuinely *subtle* rotation angles (the preset caps
   at ±30°, defaults to ±3°), not worth the added trig complexity here.
4. **`static` preset optimization**: when scale/position/rotation are all
   unchanged start→end, `zoompan`/`rotate` are skipped entirely in favor
   of a plain `scale+pad` — the same "skip the redundant filter pass"
   spirit as `video_composer`'s single-clip merge skip
   ([11-video-composer.md](11-video-composer.md)).
5. **`format=yuv420p` + `fps=` filter + `-r`/`-pix_fmt`/`-color_range tv`
   output flags** — belt-and-suspenders for "stable pixel format"/"stable
   frame rate" (see bug below). `-t duration` on the output is a hard,
   independent safety net for "deterministic duration" regardless of any
   internal zoompan frame-count rounding.

## Non-obvious design decisions

- **No shared ffmpeg wrapper exists anywhere in this codebase** (confirmed
  in [video_factory_architecture.md](video_factory_architecture.md)'s
  reconnaissance) — `scene_cutter/service.py` and `video_composer/service.py`
  each already run their own `subprocess.run(["ffmpeg"/"ffprobe", ...])`
  with no shared helper. This file follows that same established
  "copy the pattern, don't invent a cross-module wrapper" convention.
- **`duration` is a separate override parameter, not read solely from
  `MotionPlan.duration`.** A standalone `MotionPlan` has its own duration,
  but a caller driven by a Composition `Scene` has no motion-level duration
  at all — `SceneMotion` deliberately has none (see
  [22-composition-contract.md](22-composition-contract.md)), since
  `Scene.duration` is authoritative there. `duration=None` falls back to
  `motion_plan.duration`; an explicit value overrides it either way.
- **`DEFAULT_FPS`/`DEFAULT_WIDTH`/`DEFAULT_HEIGHT` are named constants
  owned by this module, not new `app.core.config.Settings` fields.**
  Nothing in this codebase has needed a video-output-format setting
  before; bolting one onto shared core config for a renderer nothing wires
  up to an endpoint yet was judged premature. When a real
  orchestrator/endpoint is built on top of this, that integration point
  decides whether to source these from Settings, a request, or a
  Composition Scene's own `OutputFormat`.
- **Uses `app.core.exceptions.FileOperationError`/`ValidationError` for
  ffmpeg failures, not a raw `RuntimeError`** the way `video_composer._run_ffmpeg`
  currently does. `app/core/exceptions.py`'s own docstring establishes typed
  exceptions as the intended service-layer convention ("raise the right
  typed error... the client gets a consistent, friendly JSON response");
  `video_composer`/`scene_cutter`'s raw-`RuntimeError` on ffmpeg failure
  predates that being consistently followed, not a pattern to replicate.

## Real bugs caught during verification

All three were found by actually running the renderer against real ffmpeg
(available in this dev environment), not just by reading the code:

1. **`ffmpeg`/`ffprobe` subprocess calls could hang indefinitely** when run
   non-interactively without `-nostdin` — reproduced directly (a corrupted
   input file left a `subprocess.run` call blocked with no output and no
   error, past a 120s wall-clock wait). Fixed by adding `-nostdin` to the
   ffmpeg invocation and `stdin=subprocess.DEVNULL` to every
   `subprocess.run` call in this file. **`scene_cutter`/`video_composer`'s
   existing ffmpeg calls have this same latent gap** (no `-nostdin`,
   default inherited stdin) — not fixed here since it's out of scope for
   this task, but worth a follow-up; see "Unresolved" below.
2. **A JPEG source rendered with `pix_fmt=yuvj420p` instead of the
   requested `yuv420p`**, even with an explicit `-pix_fmt yuv420p` — a
   JPEG decodes as full-range YUV, and ffmpeg reports the full-range
   variant's tag regardless of the requested pixel format. This meant the
   "stable pixel format" requirement silently depended on whether the
   source was a JPEG or a PNG. Fixed with an explicit `-color_range tv`
   output flag; verified identical `yuv420p` output from both a JPEG and a
   PNG source of the same content (`test_png_and_jpeg_sources_produce_identical_pixel_format`).
3. **`_probe_image`'s validation of ffprobe's output was silently wrong**:
   it checked `"x" not in output`, but ffprobe prints `"0x0"` for a file it
   can't decode at all — which still contains the character `"x"`, so a
   genuinely corrupt image passed validation and reached the full render,
   which is what actually caused bug #1's hang in practice. Fixed by
   parsing width/height as integers and requiring both `> 0`.

## Verification

Manually rendered all 9 presets against real ffmpeg on a synthetic JPEG,
confirmed via `ffprobe` that a representative output (`zoom_and_pan`,
2.5s @ 24fps, 480×852) had exactly `duration=2.500000`, `r_frame_rate=24/1`,
`nb_frames=60` (`2.5×24` exactly), `width=480`/`height=852`, and
(post-fix) `pix_fmt=yuv420p`. `python -m unittest discover -s tests` — 137
tests total (28 new: pure command/filter-graph generation covering every
code path — static-skip, zoompan-only, zoompan+rotate, all 4 easing
curves, frame-count math, deterministic output; validation-error tests
that need no ffmpeg at all — missing input, invalid output path, invalid
duration/fps/dimensions, missing-ffmpeg via mocked `shutil.which`; and a
real integration suite, skipped automatically if `ffmpeg`/`ffprobe` aren't
on `PATH`, that renders actual tiny clips and verifies their real
duration/fps/resolution/pixel-format/codec via `ffprobe`, plus the
corrupt-image and JPEG-vs-PNG pixel-format regression tests for bugs #2
and #3 above). All pass in under 6 seconds; the 109 pre-existing tests
(Beat + Asset + Motion contract + Composition) are unaffected.

## Unresolved

The stdin-hang risk (bug #1) also exists in `scene_cutter/service.py` and
`video_composer/service.py`'s own `subprocess.run(["ffmpeg", ...])` calls,
which predate this task and were not touched here (out of scope: this task
built a new renderer, not a refactor of existing modules). Worth a small,
low-risk follow-up task to add `-nostdin`/`stdin=DEVNULL` to both.
