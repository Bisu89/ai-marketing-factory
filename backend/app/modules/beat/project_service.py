"""Database-backed persistence for app.modules.beat.models.Project -- see
that module's docstring for why this is a new, separate concern from
service.py's file-based beats.json/templates.json (a real DB table,
because batch creation needs many independently-queryable projects at
once, not a single file). Uses SessionLocal directly (its own session per
call), the same pattern app.modules.video_composer.service already uses
for the exact same reason: callers include a background worker thread
(Task 13's batch beat-generation processor), not just request handlers.
"""

from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal
from app.modules.beat.models import Project
from app.modules.beat.schemas import BeatPlan, ProjectConfig, ProjectOut, new_project_draft


def slugify(text: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "-" for c in text.strip()).strip("-") or "project"
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug


def unique_project_slug(base: str, db) -> str:
    """Public (not `_`-prefixed) since the composition root (Task 13's
    batch creation -- see app/api/v1/endpoints/batch_render.py) needs to
    construct Project rows itself, inside ONE shared transaction alongside
    Batch/BatchItem rows, for real cross-table atomicity (see that file's
    own docstring for why create_project's own single-project-per-call
    shape below can't provide that on its own).
    """
    slug = slugify(base)
    candidate = slug
    suffix = 2
    while db.query(Project).filter(Project.slug == candidate).first() is not None:
        candidate = f"{slug}-{suffix}"
        suffix += 1
    return candidate


def create_project(name: str, script_text: str, config: ProjectConfig) -> int:
    """Creates a beat-less draft project (see schemas.new_project_draft) --
    the state a just-imported batch script starts in, before "Generate
    Beats for Batch" has run. Used where a single, independently-committed
    project is genuinely all that's needed (not batch creation -- see
    unique_project_slug's docstring).
    """
    db = SessionLocal()
    try:
        project = Project(
            name=name, slug=unique_project_slug(name, db), beat_plan_json=new_project_draft(script_text, name, config)
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


def _json_safe(plan: BeatPlan) -> dict:
    # mode="json" makes every value (enums, etc.) plain JSON-serializable
    # up front -- same reasoning as composition_render.py's
    # composition_request_json, rather than relying on the JSON column's
    # own encoder to know how.
    return plan.model_dump(mode="json")


def get_project(project_id: int) -> Project:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise NotFoundError("Project", project_id)
        db.expunge(project)
        return project
    finally:
        db.close()


def get_project_draft(project_id: int) -> ProjectOut:
    """Lenient read: valid even for a beat-less (not-yet-generated) project
    -- used internally by the batch beat-generation processor and by
    GET /projects/{id} (see router.py). See ProjectOut's own docstring for
    why this is a different contract from a strict BeatPlan.
    """
    project = get_project(project_id)
    return ProjectOut.model_validate({"id": project.id, "slug": project.slug, "render_job_id": project.render_job_id, **project.beat_plan_json})


def get_project_beat_plan(project_id: int) -> BeatPlan:
    """Strict read: raises if this project has no beats yet (see BeatPlan's
    own `min_length=1` invariant) -- used at render-eligibility-check time,
    where "no beats" genuinely means "not ready."
    """
    project = get_project(project_id)
    return BeatPlan.model_validate(project.beat_plan_json)


def update_project_beat_plan(project_id: int, plan: BeatPlan) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise NotFoundError("Project", project_id)
        project.beat_plan_json = _json_safe(plan)
        db.commit()
    finally:
        db.close()


def set_project_render_job_id(project_id: int, render_job_id: int) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is not None:
            project.render_job_id = render_job_id
            db.commit()
    finally:
        db.close()
