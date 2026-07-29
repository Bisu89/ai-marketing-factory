from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import app.models  # noqa: F401  (registers ORM models on Base.metadata)
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.events import EventBus
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.seed import seed_initial_data
from app.db.session import SessionLocal, engine
from app.services.download.engine import DownloadEngine
from app.services.download.http_downloader import HttpDownloader


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()

    event_bus = EventBus()
    app.state.event_bus = event_bus

    # Future modules (subtitle/story/caption/voice/affiliate/analytics generators)
    # register their event subscriptions here -- one line each, no changes to
    # DownloadEngine or any core model required. See app/modules/README.md.

    download_engine = DownloadEngine(
        downloader=HttpDownloader(),
        download_dir=Path(settings.download_dir),
        library_dir=Path(settings.library_dir),
        max_workers=settings.max_concurrent_downloads,
        event_bus=event_bus,
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
