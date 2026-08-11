"""Composition assembly + filesystem persistence -- the primary artifact is
composition.json, not a database row, same reasoning as
app.modules.beat.service's beats.json (see that module's docstring).

`build_composition_plan` is a thin, ergonomic constructor, not an
orchestrator: assembling a real CompositionPlan out of a live BeatPlan +
resolved Assets + MotionPlans + captions + audio references requires
reading from app.modules.beat/asset/motion/ai, which this module must never
import (see schemas.py's module docstring). That assembly is deliberately
left to a future application/service-level orchestrator (or the frontend)
that already has legitimate access to all of those modules at once -- the
same "composition root" pattern app/main.py and app/api/v1/router.py
already use to wire modules together without letting them import each
other. Callers of this function are expected to have already resolved
their Scenes into this module's own contract types before calling it.
"""

from pathlib import Path

from app.modules.composition.schemas import CompositionPlan, Scene


def build_composition_plan(
    scenes: list[Scene],
    *,
    video_id: int | None = None,
    narration_script: str | None = None,
    voice: str = "en-US-GuyNeural",
    language: str | None = None,
) -> CompositionPlan:
    return CompositionPlan(
        scenes=scenes,
        video_id=video_id,
        narration_script=narration_script,
        voice=voice,
        language=language,
    )


def save_composition_json(plan: CompositionPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")


def load_composition_json(path: Path) -> CompositionPlan:
    return CompositionPlan.model_validate_json(path.read_text(encoding="utf-8"))
