# 33 — Motion Presets + Beat → Motion Assignment

**Commit:** _(fill in after commit)_

## What it does

Adds a `motion_preset` field to the Beat contract (6 presets: `STATIC`,
`SLOW_PUSH_IN`, `SLOW_PULL_OUT`, `PAN_LEFT`, `PAN_RIGHT`, `ZOOM_AND_PAN`,
defaulting to `STATIC`) and a working "Motion" selector on the Visual step,
so a Beat's camera-movement choice is now part of the persisted domain
contract, not just a render-time-only frontend convenience. **No FFmpeg,
no rendering** -- this only defines and persists the choice; the next task
renders it.

## An important pre-existing-code correction

This task's brief assumed a green-field ("Do NOT blindly create
`modules/motion/` if the existing architecture has a better established
location -- inspect first"). `app/modules/motion/` **already exists**
(built several tasks ago -- [21](21-motion-domain-presets.md),
[23](23-local-motion-renderer.md)): a full `MotionPlan` contract (9
lowercase presets, numeric scale/position/rotation ranges) plus a real,
already-integrated local ffmpeg renderer, already wired into the render
pipeline via `composition_render.py`. That module was correctly **not**
touched or duplicated here -- this task only concerns whether *Beat itself*
(not Composition/Motion) can declare a preset choice that survives
`beats.json`, which it previously could not.

## Motion contract: deliberately a second, smaller enum

`Beat.motion_preset` uses a **new, Beat-local `BeatMotionPreset` enum**
(6 uppercase values), not an import of `app.modules.motion.schemas
.MotionPresetName` (9 lowercase values) -- importing it would violate
`app.modules.beat`'s "never import another module" rule. This mirrors how
`app.modules.composition.schemas.SceneMotion.preset_name` already treats a
motion preset as a loosely-coupled label rather than a shared enum
reference. All 6 `BeatMotionPreset` values share a spelling with a
`MotionPresetName` member (just cased differently), so resolving one into
the other at the one place that needs to (building a render-time `Scene`)
is a plain `.toLowerCase()`, never a partial/fallback mapping.

`motion_preset` is a **required field with a default** (`= STATIC`), not
`Optional[...] = None`: "no motion" is always a real, valid, deterministic
value, never an unset state anything downstream has to branch on. This is
also exactly what makes old `beats.json` files with no `motion_preset` key
at all keep loading with zero migration -- Pydantic fills in the default
for an absent key.

## UI

The Visual step's existing "Motion preset" dropdown (previously a
render-time-only field with 9 choices, never saved) was narrowed to the 6
`BeatMotionPreset` values and now drives the same field that persists.
Below it, a one-line description (`BEAT_MOTION_PRESET_DESCRIPTIONS`) shows
what the selected preset does. A disabled "Preview motion (renderer coming
next)" button with an explanatory tooltip replaces the old placeholder --
per this task's explicit "do not fake a rendered MP4" instruction. The
Beat sidebar (Step 2) already showed a motion label per beat from earlier
work; it now reads from the same 6-preset labels.

## Persistence

`WorkingBeat.motionPreset` (frontend) round-trips through `Beat.motion_preset`
(backend) exactly like `asset_id`/`visual_hint` already do: `toBeatDTO()`
includes it in the save payload, `workingBeatFromDTO()` reads it back on
load or after AI generation (which never sets it, so generated beats are
always `STATIC` until the user picks something).

## Compatibility

Confirmed with a **real, pre-existing** `beats.json` on disk (written
before this task, containing zero `motion_preset` keys) -- loading it
showed all 5 beats as "Static" in both the Beat list and the Visual step's
dropdown, with no console errors and no file mutation from the load alone
(the file on disk is only rewritten on an explicit Save, which is the
existing, expected persistence mechanism).

## Tests

Backend: 5 new tests in `test_schemas.py` -- all 6 presets valid, an
unknown preset rejected, missing-key defaults to `STATIC`, and two
dedicated backward-compatibility tests loading old-shape JSON at both the
`Beat` and `BeatPlan` level (plus the existing serialization test updated
to assert `motion_preset` round-trips). `python -m unittest discover -s
tests` -- **262 tests, all passing** (257 prior + 5 new).

Frontend: no test framework in this repo -- verified manually (below).

## Manual verification

Real Playwright run in two parts. **Part A (backward compatibility):**
loaded the genuine pre-existing 5-beat `beats.json` (no `motion_preset`
keys) -- every beat showed "Static" in both the sidebar and the Visual
step's dropdown, zero console errors. **Part B (5-preset assignment):**
set beat 1→Slow Push In, 2→Pan Right, 3→Slow Pull Out, 4→Zoom + Pan,
5→Static; confirmed descriptions updated per selection, the disabled
Preview button is genuinely inert, the sidebar reflected each choice,
Save succeeded, and a full page reload restored all 5 assignments exactly
-- corroborated by reading `beats.json` directly off disk afterward and
confirming the persisted `motion_preset` values matched what was set
through the UI. All 13 checks passed, zero bugs, zero console errors.

## Next task

Task 6 -- Local Motion Renderer with FFmpeg.
