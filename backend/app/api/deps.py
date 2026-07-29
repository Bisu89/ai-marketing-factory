from fastapi import Request

from app.core.config import Settings, get_settings
from app.core.events import EventBus
from app.db.session import get_db
from app.services.download.engine import DownloadEngine


def get_download_engine(request: Request) -> DownloadEngine:
    return request.app.state.download_engine


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


__all__ = ["get_db", "get_settings", "Settings", "get_download_engine", "get_event_bus"]
