from pathlib import Path

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.events import EventBus
from app.db.session import get_db
from app.services.download.engine import DownloadEngine
from app.services.insights.publish_log_service import PublishLogService
from app.services.library.service import CategoryService, EmotionService, TagService, VideoLibraryService


def get_download_engine(request: Request) -> DownloadEngine:
    return request.app.state.download_engine


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_video_library_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VideoLibraryService:
    return VideoLibraryService(db, Path(settings.library_dir))


def get_tag_service(db: Session = Depends(get_db)) -> TagService:
    return TagService(db)


def get_category_service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(db)


def get_emotion_service(db: Session = Depends(get_db)) -> EmotionService:
    return EmotionService(db)


def get_publish_log_service(db: Session = Depends(get_db)) -> PublishLogService:
    return PublishLogService(db)


__all__ = [
    "get_db",
    "get_settings",
    "Settings",
    "get_download_engine",
    "get_event_bus",
    "get_video_library_service",
    "get_tag_service",
    "get_category_service",
    "get_emotion_service",
    "get_publish_log_service",
]
