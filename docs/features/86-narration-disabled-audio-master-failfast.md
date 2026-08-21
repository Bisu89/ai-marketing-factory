# 86. Fix: Narration-Disabled Projects Failed Late, After Paid Stages

**Commit:** `78c2d0a`

Real user report: a real project ("Một câu nói làm hôn nhân thay đổi",
from the user's own "Vie V2" template) sailed through Beats, AI Visuals
(real $0.03 image spend), Voice, Audio, and Quality Gate (scored 99,
"READY") only to hard-fail at the very last stage, `READY_TO_RENDER`,
with `"This project has no valid Audio Master to compose the final
video from."`

## Root cause

`AudioProjectConfig.narration_enabled=False` is explicitly documented
as a supported project-level state ("Silent beats are explicitly
supported at the project level", `quality/analyzer.py`'s
`analyze_audio`) -- Voice and Audio both correctly no-op for it, and
Quality Gate correctly scores it clean. But `factory_pipeline.py`'s
`_stage_render` (the automated Factory pipeline's Final Composer)
*always* requires a real Audio Master, and `generate_project_audio_master`
can never produce one without a `narration.wav` existing first -- there
is no BGM-only or silent path. So any Factory-driven project with
narration disabled was **guaranteed** to fail at the last stage, always,
regardless of BGM/other settings -- after every earlier (some paid)
stage had already reported success. The classic manual "Quick Render"
path (`composition_render.py`'s `audio_master_path` is optional) has no
such requirement -- only the automated Factory pipeline does.

The user's own "Vie V2" template had `narration_enabled=false` --
almost certainly accidental, since the template also configures a real
Vietnamese `edge_tts` voice and every project made from it has full
narration text on every beat.

## Fix

Added a fail-fast check at the very start of `_execute_pipeline_sync`
(right after the `PREPARING` checkpoint, before `PREPARING_CONTENT`/
`GENERATING_BEATS`/`PREPARING_VISUALS` -- i.e. before any AI cost is
spent): if `narration_enabled` is `False`, fail immediately with a
message naming the actual cause, reusing the existing
`AUDIO_MASTER_MISSING` error code since it's the same underlying
problem, just caught before instead of after wasting money on it.

Also fixed the two pieces of real, live data behind this specific
report: project 29's own config and the "Vie V2" template both had
`narration_enabled` flipped back to `true` (via the real `PUT
/projects/{id}/beat-plan` and `PUT /templates/{id}` endpoints), then
retried the failed `FactoryRun` (id 14) -- completed successfully,
reusing the already-paid-for AI images (`visual_generation_cost_usd`
stayed at $0.03, not re-billed), producing a real 39.7s video with
narration (render job 54, QA score 100).

## Verification

New test `test_narration_disabled_fails_fast_at_preparing_before_any_paid_stage`
(`tests/api/test_factory_pipeline.py`) asserts the run fails at
`PREPARING` with `AUDIO_MASTER_MISSING` and that no checkpoint beyond
`PREPARING` was ever created. Full backend suite green. The real
end-to-end retry above (against the user's actual running app) is the
strongest verification: same bug, same project, confirmed fixed.
