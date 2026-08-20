from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.content_strategy.schemas import (
    FormatOut,
    IdeaCreateIn,
    IdeaListResponse,
    IdeaOut,
    IdeaUpdateIn,
    PillarOut,
)
from app.modules.content_strategy.service import FormatService, IdeaService, PillarService

router = APIRouter()


def get_pillar_service(db: Session = Depends(get_db)) -> PillarService:
    return PillarService(db)


def get_format_service(db: Session = Depends(get_db)) -> FormatService:
    return FormatService(db)


def get_idea_service(db: Session = Depends(get_db)) -> IdeaService:
    return IdeaService(db)


@router.get("/content-pillars", response_model=list[PillarOut])
def list_pillars(service: PillarService = Depends(get_pillar_service)):
    return service.list()


@router.get("/content-formats", response_model=list[FormatOut])
def list_formats(
    pillar_id: int | None = None,
    service: FormatService = Depends(get_format_service),
):
    return service.list(pillar_id)


@router.get("/content-ideas", response_model=IdeaListResponse)
def list_ideas(
    pillar_id: int | None = None,
    format_id: int | None = None,
    status: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    service: IdeaService = Depends(get_idea_service),
):
    items, total = service.list_ideas(
        pillar_id=pillar_id,
        format_id=format_id,
        status=status,
        min_score=min_score,
        max_score=max_score,
        page=page,
        page_size=page_size,
    )
    return IdeaListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/content-ideas", response_model=IdeaOut, status_code=201)
def create_idea(payload: IdeaCreateIn, service: IdeaService = Depends(get_idea_service)):
    return service.create_idea(
        pillar_id=payload.pillar_id,
        format_id=payload.format_id,
        title=payload.title,
        premise=payload.premise,
        target_emotion_id=payload.target_emotion_id,
        commercial_intent=payload.commercial_intent,
        status=payload.status,
    )


@router.get("/content-ideas/{idea_id}", response_model=IdeaOut)
def get_idea(idea_id: int, service: IdeaService = Depends(get_idea_service)):
    return service.get_idea(idea_id)


@router.patch("/content-ideas/{idea_id}", response_model=IdeaOut)
def update_idea(
    idea_id: int,
    payload: IdeaUpdateIn,
    service: IdeaService = Depends(get_idea_service),
):
    return service.update_idea(
        idea_id,
        title=payload.title,
        premise=payload.premise,
        target_emotion_id=payload.target_emotion_id,
        commercial_intent=payload.commercial_intent,
        score=payload.score,
        status=payload.status,
    )


@router.delete("/content-ideas/{idea_id}", status_code=204)
def delete_idea(idea_id: int, service: IdeaService = Depends(get_idea_service)):
    service.delete_idea(idea_id)
