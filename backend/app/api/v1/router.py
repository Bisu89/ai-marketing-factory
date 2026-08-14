from fastapi import APIRouter

from app.api.v1.endpoints import (
    batch_render,
    beat_generate,
    beat_preview,
    categories,
    composition_render,
    dashboard,
    detect,
    downloads,
    emotions,
    health,
    insights,
    performance,
    publish_log,
    quality_gate,
    settings,
    tags,
    videos,
)
from app.modules.ai.caption.router import router as caption_router
from app.modules.ai.hook.router import router as hook_router
from app.modules.ai.story.router import router as story_router
from app.modules.asset.router import router as asset_router
from app.modules.batch.router import router as batch_router
from app.modules.beat.router import router as beat_router
from app.modules.scene_cutter.router import router as scene_cutter_router
from app.modules.video_composer.router import router as video_composer_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(downloads.router, tags=["downloads"])
api_router.include_router(videos.router, tags=["videos"])
api_router.include_router(categories.router, tags=["categories"])
api_router.include_router(emotions.router, tags=["emotions"])
api_router.include_router(tags.router, tags=["tags"])
api_router.include_router(detect.router, tags=["detect"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(insights.router, tags=["insights"])
api_router.include_router(publish_log.router, tags=["publish-log"])
api_router.include_router(performance.router, tags=["performance"])
api_router.include_router(scene_cutter_router, tags=["scene-cutter"])
api_router.include_router(video_composer_router, tags=["video-composer"])
api_router.include_router(story_router, tags=["story"])
api_router.include_router(hook_router, tags=["hook"])
api_router.include_router(caption_router, tags=["caption"])
api_router.include_router(asset_router, tags=["asset"])
api_router.include_router(beat_router, tags=["beat"])
api_router.include_router(composition_render.router, tags=["composition-render"])
api_router.include_router(beat_generate.router, tags=["beat-generate"])
api_router.include_router(beat_preview.router, tags=["beat-preview"])
api_router.include_router(batch_router, tags=["batch"])
api_router.include_router(batch_render.router, tags=["batch-render"])
api_router.include_router(quality_gate.router, tags=["quality-gate"])
api_router.include_router(dashboard.router, tags=["dashboard"])
