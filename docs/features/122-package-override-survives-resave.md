# 122. Manual Title/Description Survive a Factory Re-Render

**Commit:** `_pending_`

Real user report: pinned a `manual_title` on a project, re-ran the Factory,
and the finished `metadata.json` still had the AI-written title.

## Cause

`set_project_package_overrides` (Task 27) writes `manual_title` /
`manual_description` / `manual_hashtags` straight into
`Project.beat_plan_json`. But every Factory stage that persists updated
beats/timing (`_stage_generate_beats`, `imagegen_generate`,
`voice_generate`, and the resume paths in `factory_pipeline`) does it by
reconstructing a fresh `BeatPlan(script_text=…, beats=…, idea=…,
content_brief=…, script_locked=…)` and calling `update_project_beat_plan`.
None of those 8 call sites pass the three package-override fields, so each
re-save wrote them back as their `None` default — silently wiping the
user's pinned title. Exactly the class of bug Task 21's
`idea`/`content_brief`/`script_locked` already hit (feature 47), for
fields added later (Task 27) than those call sites.

## Fix

One place, not 8: `update_project_beat_plan` now carries forward an
existing `manual_*` value whenever the incoming `BeatPlan` leaves it
`None`. Safe because nothing except `set_project_package_overrides` ever
sets these, and clearing an override also goes through that function
(there is no Beat-Editor UI that blanks a manual title) — so "incoming
None" always means "this caller isn't touching overrides", never "clear
it".

## Key files

- `backend/app/modules/beat/project_service.py` — `update_project_beat_plan` merge-on-None
- `backend/tests/modules/beat/test_project_service.py` (new) — 4 tests

## Verification

New `test_project_service.py` green; full `tests/api/test_package_stage.py`
(27, incl. the manual-override cases) green. Also fixed the user's live
project (#68) after the fact via `set_package_overrides` +
`regenerate-package` (no re-render needed — metadata is a leaf).
