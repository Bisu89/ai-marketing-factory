"""Cross-module orchestration ("composition roots"): the one place a
Script/Story/News flow is allowed to import app.modules.beat / batch /
asset / quality / video_composer / ai together and drive them end to end.

These files used to live under app/api/v1/endpoints/ (they carry an
APIRouter for their own HTTP surface) but their real job is sequencing +
FactoryRun/StoryRun state persistence, not "parse request -> call service
-> map response". They were moved here so the endpoints layer is HTTP-only
again and this orchestration is findable.

Still-open follow-up: the reusable per-stage helpers they import
(generate_beat_plan, run_quality_check, render_composition,
generate_project_*) still live in app/api/v1/endpoints/*_generate.py --
pulling those into their owning app.modules.<x> is a later pass.
"""
