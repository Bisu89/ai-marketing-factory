from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  (registers ORM models on Base.metadata)
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.events import EventBus
from app.core.exceptions import ExternalServiceError, FileOperationError, NotFoundError, ValidationError
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.seed import seed_initial_data
from app.db.session import SessionLocal, engine
from app.modules.scene_cutter.service import SceneCutterService
from app.modules.video_composer.service import VideoComposerService
from app.services.download.engine import DownloadEngine
from app.services.download.ytdlp_downloader import YtdlpDownloader


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
        downloader=YtdlpDownloader(),
        download_dir=Path(settings.download_dir),
        library_dir=Path(settings.library_dir),
        max_workers=settings.max_concurrent_downloads,
        event_bus=event_bus,
    )
    download_engine.start()
    app.state.download_engine = download_engine

    scene_cutter_service = SceneCutterService(library_dir=Path(settings.library_dir))
    scene_cutter_service.start()
    app.state.scene_cutter_service = scene_cutter_service

    video_composer_service = VideoComposerService(library_dir=Path(settings.library_dir))
    video_composer_service.start()
    app.state.video_composer_service = video_composer_service

    yield

    download_engine.shutdown()
    scene_cutter_service.shutdown()
    video_composer_service.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Local-only desktop app: the frontend dev server (Vite, typically :5173)
    # and this API (typically :8000) are different origins in the browser's
    # eyes even though both run on the same machine -- CORS must allow it.
    app.add_middleware(
        CORSMiddleware,
        # Vite picks the next free port if 5173 is busy, so match any
        # localhost port rather than hardcoding one -- still local-only safe.
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # StaticFiles requires the directory to exist at mount time, which happens
    # before the lifespan startup that would otherwise create it -- ensure it
    # exists here too (idempotent, DownloadEngine.start() also does this).
    library_dir = Path(settings.library_dir)
    library_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=library_dir), name="media")

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def handle_validation(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(FileOperationError)
    async def handle_file_operation(request: Request, exc: FileOperationError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": f"File operation failed: {exc}"})

    @app.exception_handler(ExternalServiceError)
    async def handle_external_service(request: Request, exc: ExternalServiceError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    return app


app = create_app()
