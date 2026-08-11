"""Filesystem persistence for a BeatPlan -- the primary artifact is
beats.json, not a database row (see schemas.py's module docstring for why).
Deliberately just two pure functions: no DB session, no FastAPI Depends, no
Settings coupling -- callers decide where beats.json lives, the same way a
future asset/motion step will decide where its own rendered clips live.
"""

from pathlib import Path

from app.modules.beat.schemas import BeatPlan


def save_beats_json(plan: BeatPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")


def load_beats_json(path: Path) -> BeatPlan:
    return BeatPlan.model_validate_json(path.read_text(encoding="utf-8"))
