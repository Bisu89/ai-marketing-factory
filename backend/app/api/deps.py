from fastapi import Request

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.download.engine import DownloadEngine


def get_download_engine(request: Request) -> DownloadEngine:
    return request.app.state.download_engine


__all__ = ["get_db", "get_settings", "Settings", "get_download_engine"]
