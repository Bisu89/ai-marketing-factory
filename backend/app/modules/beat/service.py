"""Filesystem persistence for a BeatPlan -- the primary artifact is
beats.json, not a database row (see schemas.py's module docstring for why).
Deliberately just two pure functions: no DB session, no FastAPI Depends, no
Settings coupling -- callers decide where beats.json lives, the same way a
future asset/motion step will decide where its own rendered clips live.

Custom-template persistence (Task 12 -- see
docs/features/39-project-templates.md) follows the exact same shape:
templates.json next to beats.json, not a database table -- consistent with
"do not introduce a database table if a JSON file is more consistent with
the current desktop architecture" and this module's own established
convention.
"""

from pathlib import Path

from pydantic import TypeAdapter

from app.core.exceptions import ValidationError
from app.modules.beat.schemas import BUILTIN_TEMPLATE_IDS, BeatPlan, Template

_TEMPLATE_LIST_ADAPTER = TypeAdapter(list[Template])


def save_beats_json(plan: BeatPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")


def load_beats_json(path: Path) -> BeatPlan:
    return BeatPlan.model_validate_json(path.read_text(encoding="utf-8"))


def load_custom_templates(path: Path) -> list[Template]:
    """Custom (builtin=False) templates only -- built-ins are fixed Python
    constants (schemas.BUILTIN_TEMPLATES), never written to or read from
    this file. Missing file = no custom templates yet, not an error (same
    "first use is a normal, expected state" convention as
    beat/router.py's GET /beat-plan returning None).
    """
    if not path.exists():
        return []
    return _TEMPLATE_LIST_ADAPTER.validate_json(path.read_text(encoding="utf-8"))


def save_custom_template(template: Template, path: Path) -> list[Template]:
    """Adds or replaces one custom template by id and persists the whole
    list -- templates.json is small (a handful of entries at most), so
    there's no reason for a more granular update. Rejects reusing a
    built-in's id so a custom template can never shadow/overwrite one.
    """
    if template.id in BUILTIN_TEMPLATE_IDS:
        raise ValidationError(f"Template id {template.id!r} is reserved for a built-in template.")
    templates = [t for t in load_custom_templates(path) if t.id != template.id]
    templates.append(template)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TEMPLATE_LIST_ADAPTER.dump_json(templates, indent=2).decode("utf-8"), encoding="utf-8")
    return templates


def delete_custom_template(template_id: str, path: Path) -> list[Template]:
    if template_id in BUILTIN_TEMPLATE_IDS:
        raise ValidationError(f"Template id {template_id!r} is a built-in template and cannot be deleted.")
    templates = [t for t in load_custom_templates(path) if t.id != template_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TEMPLATE_LIST_ADAPTER.dump_json(templates, indent=2).decode("utf-8"), encoding="utf-8")
    return templates
