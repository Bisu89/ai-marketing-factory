from fastapi import APIRouter

from app.api.v1.endpoints import categories, downloads, health, tags, videos

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(downloads.router, tags=["downloads"])
api_router.include_router(videos.router, tags=["videos"])
api_router.include_router(categories.router, tags=["categories"])
api_router.include_router(tags.router, tags=["tags"])
