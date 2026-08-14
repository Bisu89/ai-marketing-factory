"""Persistence for the single, current Video Factory BeatPlan: `beats.json`
next to the rest of this app's local data (see `_video_composer`'s own
`library_dir / "_video_composer"` convention in
app/modules/video_composer/service.py for the precedent this mirrors).

There's no multi-project management here -- only one BeatPlan is ever "the"
current one, matching this task's own "keep it focused, no VideoFactoryService"
scope. GET/PUT operate on the whole document (never per-beat endpoints):
PUT's request body is validated by FastAPI against BeatPlan itself before
this module's code ever runs, so "invalid beats.json can't be saved" falls
out of the existing Pydantic contract for free, with nothing duplicated.

Per app/modules/README.md, this module must never import another module --
only app.core (Settings/exceptions), same as every other module's router.
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError as PydanticValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.beat.project_service import create_project, get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import BUILTIN_TEMPLATE_IDS, BUILTIN_TEMPLATES, BeatPlan, ProjectConfig, ProjectOut, Template
from app.modules.beat.service import (
    delete_custom_template,
    load_beats_json,
    load_custom_templates,
    save_beats_json,
    save_custom_template,
)

router = APIRouter()


def _beats_json_path(settings: Settings) -> Path:
    return Path(settings.library_dir) / "_beat" / "beats.json"


def _templates_json_path(settings: Settings) -> Path:
    return Path(settings.library_dir) / "_beat" / "templates.json"


@router.get("/beat-plan", response_model=BeatPlan | None)
def get_beat_plan(settings: Settings = Depends(get_settings)) -> BeatPlan | None:
    # None (200, empty body) rather than a 404 -- "no draft saved yet" is a
    # normal, expected state for this singleton resource on first use, not
    # an error condition the frontend needs to branch its error handling on.
    path = _beats_json_path(settings)
    if not path.exists():
        return None
    try:
        return load_beats_json(path)
    except PydanticValidationError as exc:
        # A corrupted/hand-edited beats.json shouldn't surface as a raw 500 --
        # report it the same way an invalid PUT body would.
        raise ValidationError(f"Saved beats.json is not a valid BeatPlan: {exc}") from exc


@router.put("/beat-plan", response_model=BeatPlan)
def put_beat_plan(payload: BeatPlan, settings: Settings = Depends(get_settings)) -> BeatPlan:
    save_beats_json(payload, _beats_json_path(settings))
    return payload


# -- Projects (Task 13 -- see docs/features/40-batch-video-creation.md) ------
#
# Real, independently-addressable projects -- unlike the singleton
# beats.json above (untouched, still the interactive single-project
# editing session), each Project has its own row/id, created in bulk by a
# Batch (composition-root -- see app/api/v1/endpoints/batch_render.py,
# which is the only place that creates a Project alongside a BatchItem in
# the same transaction). This router only ever touches ONE project at a
# time by id, via app.modules.beat.project_service -- it has no idea a
# Batch/BatchItem exists (app.modules.beat must never import
# app.modules.batch).


class CreateProjectRequest(BaseModel):
    name: str
    script_text: str
    template_id: str = "custom"


def _resolve_template_config(template_id: str, settings: Settings) -> ProjectConfig:
    templates = {t.id: t for t in [*BUILTIN_TEMPLATES, *load_custom_templates(_templates_json_path(settings))]}
    if template_id not in templates:
        raise NotFoundError("Template", template_id)
    return templates[template_id].config.model_copy(deep=True)


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project_endpoint(payload: CreateProjectRequest, settings: Settings = Depends(get_settings)) -> ProjectOut:
    """A single-project counterpart to batch creation's own per-item Project
    row (see app/api/v1/endpoints/batch_render.py's create_batch) -- reuses
    the exact same app.modules.beat.project_service.create_project this
    codebase already has, just called for one project outside of a batch
    (Task 18's "New Video" one-click flow needs a real, id-addressable
    Project to attach a FactoryRun to; the classic singleton beats.json
    flow above has no id at all). No beats yet (a real, valid lifecycle
    state -- see ProjectOut's own docstring); the caller generates them
    next, either manually or via FactoryPipeline.
    """
    if not payload.name.strip():
        raise ValidationError("Project name must not be blank.")
    if not payload.script_text.strip():
        raise ValidationError("Script must not be blank.")
    config = _resolve_template_config(payload.template_id, settings)
    project_id = create_project(payload.name, payload.script_text, config)
    return get_project_draft(project_id)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int) -> ProjectOut:
    return get_project_draft(project_id)


@router.put("/projects/{project_id}/beat-plan", response_model=BeatPlan)
def put_project_beat_plan(project_id: int, payload: BeatPlan) -> BeatPlan:
    update_project_beat_plan(project_id, payload)
    return payload


# -- Project templates (Task 12 -- see docs/features/39-project-templates.md) -


@router.get("/templates", response_model=list[Template])
def list_templates(settings: Settings = Depends(get_settings)) -> list[Template]:
    # Built-ins first (fixed Python constants, always present, never
    # mutated by this endpoint) then any user-created custom templates.
    return [*BUILTIN_TEMPLATES, *load_custom_templates(_templates_json_path(settings))]


class CreateTemplateRequest(BaseModel):
    name: str
    description: str = ""
    config: ProjectConfig


def _slugify(name: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "_" for c in name.strip()).strip("_") or "template"
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug


@router.post("/templates", response_model=Template, status_code=201)
def create_template(payload: CreateTemplateRequest, settings: Settings = Depends(get_settings)) -> Template:
    if not payload.name.strip():
        raise ValidationError("Template name must not be blank.")

    path = _templates_json_path(settings)
    existing_ids = BUILTIN_TEMPLATE_IDS | {t.id for t in load_custom_templates(path)}
    base_slug = _slugify(payload.name)
    template_id = base_slug
    suffix = 2
    while template_id in existing_ids:
        template_id = f"{base_slug}_{suffix}"
        suffix += 1

    # "Save as Template" always creates version=1 -- there is no template
    # migration/versioning system yet (Task 12 explicitly scopes that out),
    # just the field persisted for future use.
    template = Template(
        id=template_id, name=payload.name, description=payload.description,
        version=1, builtin=False, config=payload.config,
    )
    save_custom_template(template, path)
    return template


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: str, settings: Settings = Depends(get_settings)) -> None:
    if template_id in BUILTIN_TEMPLATE_IDS:
        raise ValidationError(f"Template id {template_id!r} is a built-in template and cannot be deleted.")
    path = _templates_json_path(settings)
    existing = {t.id for t in load_custom_templates(path)}
    if template_id not in existing:
        raise NotFoundError("Custom template", template_id)
    delete_custom_template(template_id, path)
