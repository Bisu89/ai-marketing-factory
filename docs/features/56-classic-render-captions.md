# 56 — Classic Render: Burned Captions for Local-Voice Quick Render / Batch Render

**Commit:** _(fill in after commit)_

Real bug found in manual testing: a video rendered via "Quick Render" /
"Render Anyway" (the classic render path, not the auto Factory pipeline)
with local-voice narration (this app's own default) had narration and
transitions but no burned-in captions, regardless of the "Enable
captions" checkbox.

## Root cause

`composition_render.py`'s classic render endpoint and `batch_render.py`'s
render loop never passed a `project_id`/`captions_ass_path` into
`render_composition()`, so `burn_subtitles` hardcoded to `False` for
local-voice narration (a pre-Task-25 assumption: "local has no
word-boundary data to caption from"). Task 25's Caption Engine
(`caption_generate.py`) already builds real captions from
`Beat.narration` + `Beat.start`/`Beat.end`, independent of TTS engine —
only the Factory pipeline (`factory_pipeline.py`'s `_stage_render`) was
ever wired to use it. Confirmed directly against a real project: a valid,
19-segment `captions.ass` already existed on disk that the classic path
simply never looked for.

## Fix

- New `_resolve_classic_render_captions()` in `composition_render.py`:
  generates (idempotent) and resolves a project's real `captions.ass`,
  never blocking the render on a caption failure.
- `create_video_compose_job_from_composition` (classic endpoint) and
  `batch_render.py`'s render loop both call it and pass the result through
  `render_composition()`'s existing (previously Factory-only)
  `project_id`/`library_dir`/`captions_ass_path` params.
- `render_composition()`'s `burn_subtitles` decision extended: local-mode
  now burns when a real `captions_ass_path` was resolved.
- `video_composer/service.py`'s `_run_job` (non-precomposed branch):
  when local narration + a real `captions_ass_path` is given, burns that
  file directly instead of writing an empty one from zero word-boundary
  data. Audio mixing is untouched — this only changes which ASS file gets
  burned.
- Frontend: `renderComposition()` now sends `project_id` + the live
  `captions_enabled` checkbox state, which previously had zero effect on
  Quick Render (only the Factory pipeline read it).

Also fixed while making this change: `tests/api/test_factory_pipeline.py`
and `test_batch_render.py`'s shared test harnesses now explicitly pin
`ai_provider="anthropic"`/`openai_api_key=None` on their test `Settings` —
without it, a developer's real `.env` (now dual-provider aware, see
`docs/features/55-dual-ai-provider.md`) silently overrode a test's
deliberately-fake Anthropic key, turning a fast auth-failure test into a
real, non-deterministic AI call.

## Verification

Real end-to-end: rendered a real local-voice project via the classic
endpoint with the fix in place, confirmed `burn_subtitles: true` on the
created job, and visually confirmed burned caption text in an extracted
video frame. Full backend suite: 1019/1019 passing.

## Next task

None specified — awaiting the next task from the user.
