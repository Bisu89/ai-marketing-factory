from fastapi import APIRouter

from app.api.v1.endpoints import categories, detect, downloads, health, tags, videos
from app.modules.scene_cutter.router import router as scene_cutter_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(downloads.router, tags=["downloads"])
api_router.include_router(videos.router, tags=["videos"])
api_router.include_router(categories.router, tags=["categories"])
api_router.include_router(tags.router, tags=["tags"])
api_router.include_router(detect.router, tags=["detect"])
api_router.include_router(scene_cutter_router, tags=["scene-cutter"])
