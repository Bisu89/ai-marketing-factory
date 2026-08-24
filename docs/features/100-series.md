# 100. Series: Group Episodes Under a Shared Character/Visual Description

**Commit:** `ac39d65`

Real user request for a "100-Day Series Engine" (AI-planned 100-day story
arc, character bible, continuity validation, weekly compilations, milestone
videos, Day-100 finale, originality QC, YouTube analytics, a learning loop).
A review of that spec against this codebase found most of it either has no
precedent here (stateful/arc-referencing AI generation, YouTube upload/
analytics genuinely don't exist) or a real technical blocker: the image
pipeline only does *style* consistency (a shared text suffix), not *identity*
consistency (no reference-image/seed/embedding mechanism) — so "the same
face for 100 days" isn't achievable with today's image generation regardless
of how the feature was built.

**User's explicit scope-down**, implemented here: drop the AI-planned arc,
continuity/originality QC, and analytics/learning loop entirely. Episodes
are still each created exactly like the existing "New Video" flow (own
title + script, no AI-generated story). The only new capability: a
**Series** — a persistent name + character/visual description — that
episodes can attach to, so their AI-generated images share one description
(style-level consistency, not a guarantee of pixel-identical faces).

## Design

- New, deliberately tiny `app/modules/series/` module (`Series`: id, name,
  character_description — no status/state machine, since a Series never
  "completes," unlike `Batch`, which was confirmed the wrong model to
  repurpose: its whole shape assumes N items created together in one
  transaction and never growing).
- `beat.models.Project` gains two bare, unconstrained columns —
  `series_id` (indexed), `episode_number` — mirroring `render_job_id`'s own
  no-FK/no-cross-module-import shape exactly (`app.modules.beat` must never
  import `app.modules.series`, per this codebase's module isolation rule).
- New composition root `app/api/v1/endpoints/series_project.py` (the only
  place allowed to import both `series` and `beat`, mirroring
  `batch_render.py`'s role for Batch+Project): `POST /projects/{id}/attach-series`
  folds the Series' `character_description` into that Project's own
  `VisualGenerationProjectConfig.image_style_prompt` — the exact existing
  free-text style-suffix mechanism `imagegen_generate.py`'s `_image_prompt()`
  already appends to every AI-generated beat image prompt, so no new
  prompt-building code was needed. Copied **once**, at attach time (mirrors
  `Batch.template_id`'s own "applied once, never looked up again" snapshot
  semantics) — editing a Series' description later does not retroactively
  change an already-attached episode.
- `episode_number` is auto-assigned (`max(existing) + 1`, starting at 1) —
  no manual bookkeeping, matching the ease of the existing "New Video" flow.
- `NewVideoModal.tsx` gained an optional `seriesId` prop: when opened from
  the new Series detail page's "+ New Episode" button, the created project
  is attached as a second step, before `startFactoryRun` (the Factory
  pipeline's own GENERATING_VISUALS stage reads `image_style_prompt` as
  soon as it runs, so the description must already be folded in by then).

## Real bug found during verification

`update_project_beat_plan` (the existing function every other config-editing
composition root uses) reconstructs and validates a **strict** `BeatPlan`,
whose `beats` field has a real `min_length=1` invariant. A freshly-created
project legitimately has **zero** beats yet (a real, valid lifecycle state —
see `ProjectOut`'s own docstring) — attaching a Series to a just-created
episode (the normal, expected flow) hit this validation error immediately in
this feature's own tests. Every existing caller of `update_project_beat_plan`
happened to only ever call it once beats already existed, so this gap was
invisible until now. Fixed with a new, more lenient
`project_service.update_project_config(project_id, config)` that edits only
the `config` key of the stored JSON blob directly, without ever
reconstructing/validating a `BeatPlan` — used by the attach endpoint instead.

## Key files

- `app/modules/series/` (new) — `models.py`, `schemas.py`, `service.py`, `router.py`
- `app/api/v1/endpoints/series_project.py` (new) — attach + list-episodes composition root
- `app/modules/beat/models.py` — `Project.series_id`/`episode_number`
- `app/modules/beat/project_service.py` — `set_project_series`, `update_project_config` (the bug fix above)
- `app/modules/beat/schemas.py` — `ProjectOut.series_id`/`episode_number`
- `frontend/src/pages/SeriesPage.tsx`, `SeriesDetailPage.tsx` (new)
- `frontend/src/components/NewVideoModal.tsx` — optional `seriesId` prop

## Verification

New `tests/modules/series/test_service.py` (5 tests, pure CRUD) and
`tests/api/test_series_project.py` (9 tests, composition-root level: episode
auto-numbering, character-description merge, snapshot-not-live semantics,
404s, independence from unrelated projects). Full backend suite green.
`npx tsc -b --noEmit` clean. Real end-to-end verification through the live
app: created a real Series, created 2 real projects, attached both — the
first got `episode_number=1` with `image_style_prompt` correctly set to the
character description, the second got `episode_number=2`, and
`GET /series/{id}/projects` listed both in order. No browser/screenshot
tool was available in this session to visually verify the new frontend
pages themselves (list/create-modal/detail page) — verified via a clean
`tsc` build and by closely mirroring `BatchPage.tsx`'s own already-proven
UI patterns, but this is not the same as having actually seen it render.
Cleaned up all throwaway verification data afterward.
