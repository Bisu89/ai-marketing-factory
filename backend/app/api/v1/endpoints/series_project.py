"""Series <-> Project composition root: the one place allowed to import both
app.modules.series and app.modules.beat at once (per app/modules/README.md --
neither of those modules may import the other). Mirrors
app/api/v1/endpoints/batch_render.py's own role for Batch+Project.

Attaching a Project to a Series folds the Series' own character/visual
description into that Project's existing VisualGenerationProjectConfig.
image_style_prompt -- the same free-text style-suffix mechanism
imagegen_generate.py's own _image_prompt() already appends to every
AI-generated beat image prompt, so no new prompt-building code is needed
here. This is a one-time snapshot copy at attach time (mirrors
app.modules.batch.models.Batch.template_id's own "applied once, never
looked up again" semantics) -- editing a Series' description later does
NOT retroactively change an already-attached Project's own config.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.modules.beat.models import Project
from app.modules.beat.project_service import get_project_draft, set_project_series, update_project_config
from app.modules.beat.schemas import ProjectOut
from app.modules.series.service import get_series

router = APIRouter()


class AttachSeriesRequest(BaseModel):
    series_id: int


class SeriesProjectSummary(BaseModel):
    id: int
    name: str
    episode_number: int | None
    render_job_id: int | None


def _next_episode_number(db, series_id: int) -> int:
    existing = (
        db.query(Project.episode_number)
        .filter(Project.series_id == series_id, Project.episode_number.isnot(None))
        .all()
    )
    numbers = [n for (n,) in existing]
    return (max(numbers) + 1) if numbers else 1


@router.post("/projects/{project_id}/attach-series", response_model=ProjectOut)
def attach_project_to_series(project_id: int, payload: AttachSeriesRequest) -> ProjectOut:
    series = get_series(payload.series_id)  # raises NotFoundError if missing
    draft = get_project_draft(project_id)  # raises NotFoundError if missing

    db = SessionLocal()
    try:
        episode_number = _next_episode_number(db, payload.series_id)
    finally:
        db.close()

    existing_style = draft.config.visual_generation.image_style_prompt.strip()
    combined_style = f"{existing_style} {series.character_description}".strip() if series.character_description else existing_style
    updated_config = draft.config.model_copy(update={
        "visual_generation": draft.config.visual_generation.model_copy(update={"image_style_prompt": combined_style}),
    })
    # config-only update -- a freshly-created project has no beats yet (a
    # real, valid state, see ProjectOut's own docstring), so this must NOT
    # go through update_project_beat_plan's strict BeatPlan reconstruction
    # (its beats: min_length=1 invariant would reject exactly that case --
    # a real bug found via this endpoint's own test).
    update_project_config(project_id, updated_config)
    set_project_series(project_id, payload.series_id, episode_number)

    return get_project_draft(project_id)


@router.get("/series/{series_id}/projects", response_model=list[SeriesProjectSummary])
def list_series_projects(series_id: int) -> list[SeriesProjectSummary]:
    get_series(series_id)  # raises NotFoundError if missing -- 404 before an empty-but-wrong list
    db = SessionLocal()
    try:
        projects = (
            db.query(Project)
            .filter(Project.series_id == series_id)
            .order_by(Project.episode_number)
            .all()
        )
        return [
            SeriesProjectSummary(
                id=p.id, name=p.name, episode_number=p.episode_number, render_job_id=p.render_job_id,
            )
            for p in projects
        ]
    finally:
        db.close()
