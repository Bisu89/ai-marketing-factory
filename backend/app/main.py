import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  (registers ORM models on Base.metadata)
from app.api.v1.endpoints.composition_render import render_beats_for_job
from app.api.v1.endpoints.factory_pipeline import (
    reconcile_batches_on_startup,
    reconcile_factory_runs_on_startup,
    register_factory_event_handlers,
)
from app.api.v1.router import api_router
from app.core.config import get_settings, resource_path
from app.core.events import EventBus
from app.core.exceptions import ExternalServiceError, FileOperationError, NotFoundError, ValidationError
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.migrate import run_additive_column_migrations
from app.db.seed import seed_initial_data
from app.db.session import SessionLocal, engine
from app.modules.content_strategy.seed import seed_default_pillars
from app.modules.scene_cutter.service import SceneCutterService
from app.modules.video_composer.service import VideoComposerService
from app.services.download.engine import DownloadEngine
from app.services.download.ytdlp_downloader import YtdlpDownloader


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    Base.metadata.create_all(bind=engine)
    run_additive_column_migrations(engine)

    db = SessionLocal()
    try:
        seed_initial_data(db)
        seed_default_pillars(db)
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

    # beat_renderer is injected here, not imported by video_composer itself
    # (see app/modules/README.md) -- same pluggable-strategy shape as
    # DownloadEngine(downloader=YtdlpDownloader()) above. render_beats_for_job
    # lives in the composition root (app/api/v1/endpoints/composition_render.py),
    # which alone is allowed to know about both app.modules.motion and
    # app.modules.composition. See docs/features/38-render-job-hardening.md.
    video_composer_service = VideoComposerService(
        library_dir=Path(settings.library_dir),
        beat_renderer=render_beats_for_job,
        event_bus=event_bus,
    )
    video_composer_service.start()
    app.state.video_composer_service = video_composer_service

    # Task 18 (see docs/features/44-one-click-factory-pipeline.md) --
    # register FactoryRun's render.job.* subscriptions the same way this
    # comment block above already invites future modules to, then
    # reconcile any FactoryRun left in an active status by a previous
    # process, *after* video_composer_service.start() has already settled
    # every VideoComposeJob's own state via its own crash recovery.
    register_factory_event_handlers(event_bus)
    reconcile_factory_runs_on_startup(settings)
    # Task 20 (see docs/features/46-factory-batch-engine.md) -- must run
    # after reconcile_factory_runs_on_startup, so every BatchItem still
    # "RUNNING" syncs from its FactoryRun's already-settled outcome, not a
    # stale in-flight one.
    reconcile_batches_on_startup()

    yield

    download_engine.shutdown()
    scene_cutter_service.shutdown()
    video_composer_service.shutdown()


def _prepend_bundled_ffmpeg_to_path() -> None:
    """Packaged builds ship ffmpeg.exe/ffprobe.exe under resources/ffmpeg/ so
    a customer never has to install ffmpeg themselves. Every ffmpeg/ffprobe
    call in this app -- the direct subprocess.run(["ffmpeg", ...]) calls in
    video_composer/service.py, and PySceneDetect's own internal ffmpeg call
    inside scene_cutter/service.py -- resolves the binary via PATH, so fixing
    it once here (before anything can invoke either) covers both without
    touching either module. In dev, resources/ffmpeg/ doesn't exist, so this
    is a no-op and the system's own ffmpeg (if any) is used as before.
    """
    ffmpeg_dir = resource_path("resources/ffmpeg")
    if ffmpeg_dir.exists():
        os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")


def create_app() -> FastAPI:
    _prepend_bundled_ffmpeg_to_path()

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

    # Packaged builds bundle the frontend's `npm run build` output (see
    # docs/features/14-desktop-packaging.md) and this API serves it directly
    # -- no separate Node/Vite process needed at runtime. In dev, frontend/
    # dist/ doesn't exist (the separate `npm run dev` server is used
    # instead), so this whole block is a no-op and today's dev workflow is
    # unaffected. Registered last so it never shadows /api/v1/* or /media/*
    # (Starlette matches routes in registration order).
    frontend_dir = resource_path("frontend/dist")
    if frontend_dir.exists():
        assets_dir = frontend_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            # A real static file (favicon, manifest, etc.) is served as-is;
            # anything else (a client-side route like /story) falls back to
            # index.html so react-router can handle it after load, including
            # on a hard refresh.
            candidate = frontend_dir / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dir / "index.html")

    return app


app = create_app()
