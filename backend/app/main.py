import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  (registers ORM models on Base.metadata)
from app.api.v1.endpoints.assets_cleanup import sweep_stale_render_cache
from app.api.v1.endpoints.chinese_drama_dub import generate_dub
from app.api.v1.endpoints.composition_render import render_beats_for_job
from app.api.v1.endpoints.factory_pipeline import (
    reconcile_batches_on_startup,
    reconcile_factory_runs_on_startup,
    register_factory_event_handlers,
)
from app.api.v1.router import api_router
from app.modules.affiliate.router import redirect_router as affiliate_redirect_router
from app.core.config import get_settings, resource_path
from app.core.events import EventBus
from app.core.exceptions import ExternalServiceError, FileOperationError, NotFoundError, ValidationError
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.migrate import run_additive_column_migrations
from app.db.seed import seed_initial_data
from app.db.session import SessionLocal, engine
from app.modules.content_strategy.seed import seed_default_pillars
from app.modules.news.seed import seed_default_news_sources
from app.modules.news.service import fetch_all_enabled_sources
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
        seed_default_news_sources(db)
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
    # dub_generator is injected the same way beat_renderer is (see the
    # comment above) -- generate_dub (chinese_drama_dub.py, the composition
    # root allowed to import app.modules.ai) takes `settings` as an
    # explicit param for testability, so it's bound here via a closure
    # rather than passed positionally the way DubGenerator's own 2-arg
    # call signature expects.
    video_composer_service = VideoComposerService(
        library_dir=Path(settings.library_dir),
        beat_renderer=render_beats_for_job,
        dub_generator=lambda video_path, on_transcribed: generate_dub(video_path, on_transcribed, settings),
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

    # Render-cache auto-cleanup (see app/api/v1/endpoints/assets_cleanup.py).
    # Once now, then every 24h while the app stays open -- a no-op unless
    # settings.render_cache_retention_days > 0. Daemon thread + Event so a
    # shutdown never waits up to a day for the sleep to return.
    cache_sweep_stop = threading.Event()

    def _cache_sweep_loop() -> None:
        while not cache_sweep_stop.is_set():
            try:
                sweep_stale_render_cache(get_settings())
            except Exception:  # noqa: BLE001 -- a bad sweep must never crash the app
                logging.getLogger(__name__).exception("render-cache auto-sweep failed")
            cache_sweep_stop.wait(24 * 60 * 60)

    cache_sweep_thread = threading.Thread(target=_cache_sweep_loop, name="render-cache-sweep", daemon=True)
    cache_sweep_thread.start()

    # News feed poll loop (see docs/features/123-news-channel.md). Same
    # daemon-thread + Event shape as the cache sweep above -- a no-op while
    # settings.news_poll_interval_minutes == 0 (the shipped default), so a
    # user who never opens the News page pays nothing for it.
    news_poll_stop = threading.Event()

    def _news_poll_loop() -> None:
        while not news_poll_stop.is_set():
            interval = max(0, get_settings().news_poll_interval_minutes)
            if interval <= 0:
                news_poll_stop.wait(5 * 60)  # re-check the setting every 5 min
                continue
            try:
                fetch_all_enabled_sources()
            except Exception:  # noqa: BLE001 -- a bad poll must never crash the app
                logging.getLogger(__name__).exception("news feed auto-poll failed")
            news_poll_stop.wait(interval * 60)

    news_poll_thread = threading.Thread(target=_news_poll_loop, name="news-feed-poll", daemon=True)
    news_poll_thread.start()

    yield

    cache_sweep_stop.set()
    news_poll_stop.set()
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
    # Real, short, shareable click-tracking link (Task 12 -- see
    # docs/features/77-affiliate-engine.md) -- deliberately NOT nested
    # under api_v1_prefix, since /r/{code} is meant to be pasted into a
    # social post/bio, not called as an API client.
    app.include_router(affiliate_redirect_router)

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

    @app.middleware("http")
    async def _no_store_api_responses(request: Request, call_next):
        """Every /api/v1 response is live data, never a cacheable asset.
        A packaged build once served the SPA index.html as the fallback for
        unknown /api/v1/* paths *with* ETag/Last-Modified, which browsers
        then heuristically cached and replayed even after the real endpoint
        shipped ("200 OK (from disk cache)", content-type text/html). Force
        no-store on the whole API surface so that can never recur."""
        response = await call_next(request)
        if request.url.path.startswith(settings.api_v1_prefix):
            response.headers["Cache-Control"] = "no-store"
        return response

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
