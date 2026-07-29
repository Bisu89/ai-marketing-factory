from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import Settings, get_db, get_settings

router = APIRouter()


@router.get("/health")
def health_check(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "app_name": settings.app_name,
    }
