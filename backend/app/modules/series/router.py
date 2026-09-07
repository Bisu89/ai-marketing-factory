"""Pure series-domain CRUD -- no knowledge of app.modules.beat required (see
models.py's module docstring). Attaching a Project to a Series (which needs
both this module and app.modules.beat) lives in the composition root instead
-- app/api/v1/endpoints/series_project.py -- same
"module router stays pure, composition root does cross-module work" split
app.modules.batch.router already establishes.
"""

from fastapi import APIRouter

from app.modules.series.schemas import (
    CreateSeriesRequest,
    SeriesOut,
    UpdateSeriesRequest,
    UpdateSeriesStudioRequest,
)
from app.modules.series.service import (
    create_series,
    get_series,
    list_series,
    update_series,
    update_series_studio,
)

router = APIRouter()


@router.post("/series", response_model=SeriesOut, status_code=201)
def create_series_endpoint(payload: CreateSeriesRequest) -> SeriesOut:
    series = create_series(payload.name, payload.character_description)
    return SeriesOut.model_validate(series)


@router.get("/series", response_model=list[SeriesOut])
def list_series_endpoint() -> list[SeriesOut]:
    return [SeriesOut.model_validate(s) for s in list_series()]


@router.get("/series/{series_id}", response_model=SeriesOut)
def get_series_endpoint(series_id: int) -> SeriesOut:
    return SeriesOut.model_validate(get_series(series_id))


@router.put("/series/{series_id}", response_model=SeriesOut)
def update_series_endpoint(series_id: int, payload: UpdateSeriesRequest) -> SeriesOut:
    series = update_series(series_id, payload.name, payload.character_description)
    return SeriesOut.model_validate(series)


@router.put("/series/{series_id}/studio", response_model=SeriesOut)
def update_series_studio_endpoint(series_id: int, payload: UpdateSeriesStudioRequest) -> SeriesOut:
    """AI Storytelling Studio (feature 131) -- the channel_id / branding /
    voice / metadata-convention fields. Never touches name /
    character_description.
    """
    return SeriesOut.model_validate(update_series_studio(series_id, **payload.model_dump()))
