# 26 — Video Factory Frontend Workflow

**Commit:** _(fill in after commit)_

## What it does

A single new page, **Video Factory** (`/video-factory`), that lets a user
go from a typed script to a rendered, captioned, narrated video without
leaving the browser: enter a script → generate/edit beats → assign a local
image to each beat → pick a caption style → configure audio (voice,
narration volume, background music + ducking, fades) → render → watch the
result, using the real backend pipeline built in Tasks 01–08
(Beat/Motion/Composition contracts, the local motion renderer, and the
Composition↔Video Composer integration with its audio/caption extensions).

## Key files

`frontend/src/pages/VideoFactoryPage.{tsx,css}` (new), `frontend/src/types/{videoFactory,asset}.ts`
(new), `frontend/src/api/{videoFactory,asset}.ts` (new), one added function
(`getVideoComposeJob`) in the existing `frontend/src/api/videoComposer.ts`,
five new fields mirrored onto `frontend/src/types/videoComposer.ts`'s
`VideoComposeJob` (matching Task 08's backend additions), `App.tsx` (+1
route), `Sidebar.tsx` (+1 nav entry).

## Why beat generation and preset lists are client-side, not new endpoints

`app.modules.beat` is a contract-only module with no router (Task 02);
motion/caption presets are small, stable, already-documented sets (9 and 5
values respectively) with no listing endpoint. Per this task's "keep it
simple, do not create a giant wizard framework" instruction, and its
allowance to add typed API wrappers "where backend endpoints already exist
**or are created by this feature**," the deliberate choice here was to add
**zero new backend endpoints** and instead:

- Generate beats **client-side**: split the script into sentences, estimate
  each beat's duration from word count (~150 wpm), and assign
  hook/body/cta by position — a plain TypeScript function
  (`generateBeatsFromScript`), not a network round trip.
- Hardcode the 9 motion presets and 5 caption presets (with their exact
  numeric defaults, mirrored from `app/modules/motion/service.py`'s
  `_PRESET_DEFAULTS` — see `MOTION_PRESET_DEFAULTS` in `types/videoFactory.ts`)
  directly in TypeScript, following the same "duplicate the pattern, don't
  import across a boundary that can't be crossed" convention every
  Python↔Python module boundary in this codebase already uses, extended
  here across the Python↔TypeScript boundary out of necessity.

The only backend surface this page actually calls is what already existed:
`POST /assets`, `GET /assets`, `POST /video-compose-jobs/from-composition`,
and `GET /video-compose-jobs/{id}` (the last one newly wrapped on the
frontend, though the backend route itself already existed since
`video_composer/router.py` was first built).

## Deliberate scope simplifications

- **No per-beat SFX or per-scene transition configuration in the UI** —
  every scene gets a fixed default transition (crossfade, 0.4s) and no SFX;
  `SceneAudio.sfx`/per-scene `SceneTransition` exist in the contract and
  the backend (Task 08), but exposing them wasn't one of the 10 listed
  workflow steps, and skipping them keeps the form to a single page instead
  of a step-by-step wizard.
- **No search-and-pick-existing-asset UI.** `GET /assets` search exists and
  is wrapped (`searchAssets`), but only used defensively (see the
  duplicate-path bug below) — a full "browse and pick from the library"
  picker was judged out of scope for a "minimum" workflow; a user assigns
  an asset by typing a file path and clicking "Register."
- **Fixed 1080×1920 @ 30fps output** for every scene, not exposed in the UI.
- **"Enter/select a story" is a plain textarea**, not a deep integration
  with the AI Story job-selection UI on `/ai` — the page's subtitle points
  users there to generate a script first, then paste it in, rather than
  building cross-page state.

## A real bug found only by driving the page in a browser

`Asset.path` is unique (Task 03) — registering the same file twice (e.g. a
user reusing one image across beats, or retrying after a mistake) returned
a 400 from `POST /assets` with no recovery path in the first version of
`handleRegisterAsset`. Caught by an actual Playwright run against the real
backend (not by reading the code): the fix looks the existing asset up via
`GET /assets?q=<filename>` and matches on exact `path` when registration
fails, using the existing asset's id instead of surfacing a hard error —
reusing the same file across beats, or re-registering after a page reload,
now works transparently instead of requiring a different path each time.

## A real, unrelated schema-drift bug found the same way

Starting the real backend (`uvicorn`, not just `python -c "create_app()"`,
which never runs the lifespan) for this task's manual verification hit a
`sqlite3.OperationalError: no such column: video_compose_job.narration_volume`
on startup. A `data/library.db` already existed on this machine (from
earlier sessions' work, with 0 rows in `video`/`video_compose_job`/`asset`
— confirmed safe before touching anything) predating Task 08's new columns;
`Base.metadata.create_all()` never alters existing tables. Fixed with the
same additive `ALTER TABLE` approach already documented in
[10-scene-cutter.md](10-scene-cutter.md) for the identical situation — all
6 new columns have defaults, so this was a safe, non-destructive fix, not
a schema rewrite. This is a one-time local fix to this machine's dev
database, not a code change; a fresh environment's `data/library.db` is
created correctly from scratch by `create_all()` with the new columns
already present (verified in Task 08's own test suite, which uses isolated
in-memory databases and was unaffected).

## Verification

**TypeScript**: `npx tsc -b` — zero errors.

**Manual, end-to-end, against the real backend** (not mocked): started the
real FastAPI server (`uvicorn`) and the real Vite dev server, then drove
the actual page with Playwright (Python, headless Chromium) — typed a
3-sentence script, generated 3 beats, trimmed to 2, registered 2 real
local JPEG images as assets (hitting, then recovering from, the duplicate-
path bug above), selected the "cinematic" caption preset, left
optional fields (music, output folder) empty, and clicked "Render." The
job progressed through real status transitions (queued → narrating →
subtitling → mixing_audio → finalizing → **completed**) in ~22 seconds,
using real `edge_tts` narration and the real local ffmpeg pipeline
(Tasks 06–08), and the page rendered a working `<video>` element with the
correct burned-in title, playable, correct duration (0:09, matching the
sum of the two beats' durations after transition overlap). Confirmed the
same job also appears correctly in the pre-existing `/video-composer`
page's job list (same underlying `VideoComposeJob` table/`GET` endpoint),
proving no interference between the two entry points.

**Existing pages unaffected**: navigated to `/dashboard`, `/video-composer`,
`/ai`, `/scene-cutter`, and `/library` with Playwright — all five loaded
with the correct heading and zero console/page errors, confirmed via
screenshot for `/video-composer` specifically (unchanged Vietnamese-language
UI, unchanged form).

All test artifacts (registered assets, the rendered job, its output files,
temp screenshots, temp scripts) were removed afterward; only the
6-column `ALTER TABLE` fix (a database-only change, not a code change) was
left in place, since reverting it would just reproduce the startup crash.
