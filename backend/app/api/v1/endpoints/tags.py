from fastapi import APIRouter, Depends

from app.api.deps import get_tag_service
from app.schemas.tag import TagCreateIn, TagMergeIn, TagOut, TagRenameIn
from app.services.library.service import TagService

router = APIRouter()


@router.get("/tags", response_model=list[TagOut])
def list_tags(query: str | None = None, service: TagService = Depends(get_tag_service)):
    return service.list(query)


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(payload: TagCreateIn, service: TagService = Depends(get_tag_service)):
    return service.create(payload.name)


@router.put("/tags/{tag_id}", response_model=TagOut)
def rename_tag(tag_id: int, payload: TagRenameIn, service: TagService = Depends(get_tag_service)):
    return service.rename(tag_id, payload.name)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, service: TagService = Depends(get_tag_service)):
    service.delete(tag_id)


@router.post("/tags/merge", response_model=TagOut)
def merge_tags(payload: TagMergeIn, service: TagService = Depends(get_tag_service)):
    return service.merge(payload.source_tag_id, payload.target_tag_id)
