from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import app.models  # noqa: F401  (registers ORM models on Base.metadata)
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import engine
from app.services.download.engine import DownloadEngine
from app.services.download.http_downloader import HttpDownloader


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    Base.metadata.create_all(bind=engine)

    download_engine = DownloadEngine(
        downloader=HttpDownloader(),
        download_dir=Path(settings.download_dir),
        max_workers=settings.max_concurrent_downloads,
    )
    download_engine.start()
    app.state.download_engine = download_engine

    yield

    download_engine.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
