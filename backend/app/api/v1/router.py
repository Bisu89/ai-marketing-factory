from fastapi import APIRouter

from app.api.v1.endpoints import downloads, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(downloads.router, tags=["downloads"])
