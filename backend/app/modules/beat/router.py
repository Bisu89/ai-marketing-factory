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
from pydantic import BaseModel, field_validator
from pydantic import ValidationError as PydanticValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.beat.project_service import (
    create_project,
    get_project_draft,
    update_project_beat_plan,
    update_project_idea,
    update_project_script,
)
from app.modules.beat.schemas import (
    BUILTIN_TEMPLATE_IDS,
    BUILTIN_TEMPLATES,
    CONTENT_LANGUAGES,
    MAX_OUTRO_TEXT_LENGTH,
    VISUAL_GENERATION_MODES,
    BeatPlan,
    ProjectConfig,
    ProjectOut,
    Template,
)
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
    # Task 21: exactly one of these two must be non-blank -- a project
    # starts from either a full script (classic flow, script_locked=True)
    # or a one-line idea (FactoryPipeline's CONTENT stage produces the
    # script before Beat generation ever runs -- see content_generate.py).
    script_text: str | None = None
    idea: str | None = None
    template_id: str = "custom"
    # Task 59 -- "Generate Full by AI": set once at creation time, same as
    # template_id, rather than requiring a separate config-patch call
    # afterward (a beat-less project has no BeatPlan yet -- BeatPlan.beats
    # requires at least one beat -- so update_project_beat_plan can't be
    # used to set this before GENERATING_BEATS has even run).
    visual_generation_mode: str = "library"
    # Real user report: the one-click "New Video" modal (this endpoint) had
    # no language control at all -- every built-in Template hardcodes
    # content.language="en"/voice.language="en" in its own stored config,
    # so a project created here was always English regardless of Template,
    # with no way to request e.g. Vietnamese before auto-produce started.
    # None (the default) means "use whatever the template itself says" --
    # unchanged behavior for every existing caller of this endpoint; a real
    # value here overrides the template's own language, same precedence
    # VideoFactoryPage.tsx's own Step 1 dropdown already established
    # (see buildProjectConfigForSave -- the live dropdown always wins over
    # the template's snapshot value).
    content_language: str | None = None
    # Real user follow-up to the Outro Card feature (docs/features/
    # 89-outro-card.md): "what about Generate Full by AI?" -- that flow
    # creates the Project and starts the FactoryRun in one call, before
    # there's ever a BeatPlan to attach a Step-4-style edit to (same
    # reasoning as visual_generation_mode above), so the outro has to be
    # settable here, at creation time, or not at all for this flow. None
    # (the default) means no outro, matching OutroProjectConfig's own
    # default -- unchanged behavior for every existing caller.
    outro_text: str | None = None

    @field_validator("outro_text")
    @classmethod
    def _outro_text_within_length(cls, value: str | None) -> str | None:
        if value is not None and len(value) > MAX_OUTRO_TEXT_LENGTH:
            raise ValueError(f"outro_text must be at most {MAX_OUTRO_TEXT_LENGTH} characters, got {len(value)}")
        return value


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
    script_text = (payload.script_text or "").strip() or None
    idea = (payload.idea or "").strip() or None
    if not script_text and not idea:
        raise ValidationError("Either a Script or an Idea must be provided.")
    if payload.visual_generation_mode not in VISUAL_GENERATION_MODES:
        raise ValidationError(
            f"Unknown visual_generation_mode {payload.visual_generation_mode!r}, must be one of {VISUAL_GENERATION_MODES}"
        )
    if payload.content_language is not None and payload.content_language not in CONTENT_LANGUAGES:
        raise ValidationError(f"Unknown content_language {payload.content_language!r}, must be one of {CONTENT_LANGUAGES}")

    config = _resolve_template_config(payload.template_id, settings)
    config = config.model_copy(update={"visual_generation": config.visual_generation.model_copy(
        update={"mode": payload.visual_generation_mode}
    )})
    if payload.content_language is not None:
        # Same override precedence VideoFactoryPage.tsx's own Step 1
        # dropdown already established: an explicit language choice always
        # wins over whatever the Template itself stored. Local/SAPI5 (the
        # default Voice Factory provider) only has a real voice for a
        # language if the OS shipped that voice pack -- Edge TTS has one
        # for every CONTENT_LANGUAGES entry, so switch to it automatically
        # for anything but English, matching that same dropdown's own
        # auto-switch (VideoFactoryPage.tsx's own onChange handler).
        config = config.model_copy(update={
            "content": config.content.model_copy(update={"language": payload.content_language}),
            "voice": config.voice.model_copy(update={
                "language": payload.content_language,
                "provider": "edge_tts" if payload.content_language != "en" else config.voice.provider,
            }),
        })
    if payload.outro_text is not None and payload.outro_text.strip():
        config = config.model_copy(update={
            "outro": config.outro.model_copy(update={"enabled": True, "text": payload.outro_text.strip()}),
        })
    project_id = create_project(payload.name, script_text, config, idea=idea)
    return get_project_draft(project_id)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int) -> ProjectOut:
    return get_project_draft(project_id)


class UpdateIdeaRequest(BaseModel):
    idea: str


@router.put("/projects/{project_id}/idea", response_model=ProjectOut)
def put_project_idea(project_id: int, payload: UpdateIdeaRequest) -> ProjectOut:
    """Task 21 section 16/50 -- a direct edit to the idea (not an AI call;
    see POST /projects/{id}/regenerate-script in content_generate.py for
    that). Invalidates Content/Script/Beat downstream unless the script is
    locked -- see project_service.update_project_idea's own docstring.
    """
    if not payload.idea.strip():
        raise ValidationError("Idea must not be blank.")
    update_project_idea(project_id, payload.idea)
    return get_project_draft(project_id)


class UpdateScriptRequest(BaseModel):
    script_text: str


@router.put("/projects/{project_id}/script", response_model=ProjectOut)
def put_project_script(project_id: int, payload: UpdateScriptRequest) -> ProjectOut:
    """Task 21 section 16/17 -- a direct human edit of the script. Always
    locks it (see project_service.update_project_script) so no later
    automatic content generation can overwrite it, and invalidates Beat
    downstream if the text actually changed.
    """
    if not payload.script_text.strip():
        raise ValidationError("Script must not be blank.")
    update_project_script(project_id, payload.script_text)
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


class UpdateTemplateRequest(BaseModel):
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


@router.put("/templates/{template_id}", response_model=Template)
def update_template(
    template_id: str, payload: UpdateTemplateRequest, settings: Settings = Depends(get_settings)
) -> Template:
    if template_id in BUILTIN_TEMPLATE_IDS:
        raise ValidationError(f"Template id {template_id!r} is a built-in template and cannot be edited.")
    if not payload.name.strip():
        raise ValidationError("Template name must not be blank.")

    path = _templates_json_path(settings)
    existing = {t.id: t for t in load_custom_templates(path)}
    if template_id not in existing:
        raise NotFoundError("Custom template", template_id)

    # save_custom_template already upserts by id (app/modules/beat/service.py)
    # -- editing is just "create with the same id", bumping version so any
    # future migration/versioning system (out of scope today, same as
    # create_template's own version=1) has real data to work from.
    template = Template(
        id=template_id, name=payload.name, description=payload.description,
        version=existing[template_id].version + 1, builtin=False, config=payload.config,
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
