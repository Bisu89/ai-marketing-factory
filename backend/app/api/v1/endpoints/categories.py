from fastapi import APIRouter, Depends

from app.api.deps import get_category_service
from app.schemas.category import CategoryOut
from app.services.library.service import CategoryService

router = APIRouter()


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(service: CategoryService = Depends(get_category_service)):
    return service.list()
