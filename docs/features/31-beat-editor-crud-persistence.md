# 31 — Beat Editor CRUD and Persistence

**Commit:** _(fill in after commit)_

## What it does

Makes the Video Factory's Beat Editor (Step 2/3's beat list + detail panel)
fully usable: select/add/edit/delete/reorder beats, a derived total-duration
display, a dirty-state indicator, and Save/Reload against a real
`beats.json` on disk. Previously the reorder arrows and delete button were
non-functional and there was no way to persist a BeatPlan at all.

## Key files

`backend/app/modules/beat/router.py` (new — `GET`/`PUT /beat-plan`),
`backend/app/api/v1/router.py` (+1 route), `backend/tests/modules/beat/test_router.py`
(new, 6 tests), `frontend/src/api/beat.ts` (+`loadBeatPlan`/`saveBeatPlan`),
`frontend/src/api/client.ts` (formats FastAPI's structured 422 `detail`
array into readable lines instead of raw JSON), `frontend/src/pages/VideoFactoryPage.tsx`
(+`.css`) (functional reorder/delete-with-fallback-selection, editable
visual_hint field, dirty tracking, Save button, load-on-mount).

## Beat Editor

- **Selection**: first beat auto-selected after generate/load/add; clicking
  a list item selects it; edits never change selection.
- **Add**: appends a beat with fresh, non-index-based id (`nextBeatId()`,
  unchanged from Task 2), defaults `type: BODY, duration: 3`.
- **Edit**: type/narration/duration/visual_hint all editable in the detail
  panel; local `useState` only, no per-keystroke API calls.
- **Delete**: removes only the selected beat; if it was selected, falls
  back to whichever beat now occupies the same array slot (or the new last
  beat). IDs of surviving beats are untouched; `order` is never a stored
  field kept in sync -- it's always derived from array position at render
  and at save time, so there's nothing to "renormalize."
- **Reorder**: ↑/↓ swap array positions; ids and content travel with the
  beat, never with the slot (verified: moving an empty beat up past an
  edited one leaves the edited one's content following its id, not pinned
  to its old position).
- **List display**: narration preview, or a red "No narration" warning if
  blank; a "no visual hint" warning in the meta row if unset -- no more
  `(no narration yet)` placeholder shown when text actually exists.

## Persistence

`beats.json` lives at `<library_dir>/_beat/beats.json` -- one fixed path,
mirroring `video_composer`'s own `library_dir / "_video_composer"`
convention (see `app/modules/video_composer/service.py`). There's no
multi-project system; it's a single "current draft," matching this task's
explicit scope. `GET /beat-plan` returns `null` (not a 404) when nothing's
been saved -- a normal first-run state, not an error the frontend needs to
branch on. `PUT /beat-plan` is validated by FastAPI against `BeatPlan`
itself before any handler code runs (Pydantic's own request-body
validation), so an invalid plan is rejected before `save_beats_json` is
ever called -- nothing about "is this a valid BeatPlan" is duplicated
anywhere. The frontend loads the saved plan once on mount (if any) and
lands directly on Step 2 with it; edits set a `dirty` flag; Save clears it
on success.

**Design choice — no live/continuous validation.** The domain contract
(`Beat`/`BeatPlan`'s Pydantic validators) is the only place validation
rules exist. Calling the backend on every keystroke to "validate live"
would mean constant network chatter for no benefit, since the UI's own CRUD
mechanics already make most invariants unreachable (ids are always
unique/stable, order is always contiguous by construction, type is always
a valid enum value via `<select>`). Validation is therefore checked exactly
once per meaningful action -- at Save -- and whatever the backend's
`BeatPlan` rejects is shown verbatim (now formatted as readable lines
instead of raw JSON, see `client.ts` above).

## Tests

Backend: `backend/tests/modules/beat/test_router.py`, 6 new tests --
save/load round trip, 404-replaced-by-null on first use, malformed
on-disk JSON handled as a clean 400 (not a raw 500), a second PUT
overwrites the first, an invalid `BeatPlan` construction is rejected (the
same mechanism FastAPI's own request validation uses). Ordering/duplicate-id
rules are already covered by Task 1's `test_schemas.py` and intentionally
not re-tested here. `python -m unittest discover -s tests` -- **246 tests,
all passing** (240 prior + 6 new).

Frontend: still no test framework in this repo -- verified manually (below).

## Manual verification

Real Playwright run against the live dev servers covering the task's full
scenario: add 5 beats (no API key configured, so "Add beat manually" stood
in for "Generate," a real environment constraint) → edit beat 1's
type/narration/visual_hint/duration → move a beat up twice, confirming
content follows id not slot → delete a beat, confirming renumbering and
fallback selection → add a 6th beat and edit its duration → confirm total
duration recomputes live → Save (dirty indicator flips to "Saved," real
`PUT /beat-plan` → 200) → full page reload → same 5 beats restored exactly,
landing on Step 2 automatically. All 12 checks passed, zero console errors,
zero bugs found.

## Architecture

- Beat validation stays centralized in `app.modules.beat.schemas` --
  nothing re-implements duration bounds, enum membership, or blank-text
  checks anywhere else; the frontend only does presentation-level
  normalization (blank string → `null` before sending, matching what the
  contract already expects).
- Beat ids are stable: backend-issued ids (from generate or a loaded save)
  are reused as-is by the frontend rather than replaced; manually-added
  beats get a fresh non-index id once and keep it through every
  edit/move/save/reload.
- No module-to-module imports: `app/modules/beat/router.py` only imports
  `app.core` (Settings/exceptions) and its own `schemas.py`/`service.py`.
- No unrelated refactor: the Video Factory page's step-wizard layout,
  Script/Visuals/Audio/Render steps, and all other modules are untouched.

## Next task

Task 4 -- Asset Library + Beat → Asset Assignment.
