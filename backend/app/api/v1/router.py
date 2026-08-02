from fastapi import APIRouter

from app.api.v1.endpoints import categories, detect, downloads, health, insights, settings, tags, videos
from app.modules.scene_cutter.router import router as scene_cutter_router
from app.modules.video_composer.router import router as video_composer_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(downloads.router, tags=["downloads"])
api_router.include_router(videos.router, tags=["videos"])
api_router.include_router(categories.router, tags=["categories"])
api_router.include_router(tags.router, tags=["tags"])
api_router.include_router(detect.router, tags=["detect"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(insights.router, tags=["insights"])
api_router.include_router(scene_cutter_router, tags=["scene-cutter"])
api_router.include_router(video_composer_router, tags=["video-composer"])
