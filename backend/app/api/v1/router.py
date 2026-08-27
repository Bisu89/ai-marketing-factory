from fastapi import APIRouter

from app.api.v1.endpoints import (
    affiliate_performance,
    affiliate_recommend,
    ai_costs,
    audio_generate,
    batch_render,
    beat_generate,
    beat_preview,
    caption_generate,
    categories,
    competitor_analysis,
    composition_render,
    content_batch_generate,
    content_generate,
    content_idea_generation,
    content_recommendations,
    dashboard,
    detect,
    downloads,
    emotions,
    factory_pipeline,
    final_qa,
    health,
    insights,
    publish_log,
    motion_generate,
    package_generate,
    performance_intelligence,
    produced_videos,
    quality_gate,
    series_project,
    settings,
    winner_detection,
    tags,
    videos,
    voice_generate,
)
from app.modules.ai.hook.router import router as hook_router
from app.modules.ai.story.router import router as story_router
from app.modules.asset.router import router as asset_router
from app.modules.batch.router import router as batch_router
from app.modules.beat.router import router as beat_router
from app.modules.affiliate.router import router as affiliate_router
from app.modules.competitor_intelligence.router import router as competitor_intelligence_router
from app.modules.content_strategy.router import router as content_strategy_router
from app.modules.scene_cutter.router import router as scene_cutter_router
from app.modules.series.router import router as series_router
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
api_router.include_router(performance_intelligence.router, tags=["performance-intelligence"])
api_router.include_router(winner_detection.router, tags=["winner-detection"])
api_router.include_router(content_recommendations.router, tags=["content-recommendations"])
api_router.include_router(ai_costs.router, tags=["ai-costs"])
api_router.include_router(competitor_intelligence_router, tags=["competitor-intelligence"])
api_router.include_router(competitor_analysis.router, tags=["competitor-analysis"])
api_router.include_router(affiliate_router, tags=["affiliate"])
api_router.include_router(affiliate_recommend.router, tags=["affiliate-recommend"])
api_router.include_router(affiliate_performance.router, tags=["affiliate-performance"])
api_router.include_router(scene_cutter_router, tags=["scene-cutter"])
api_router.include_router(video_composer_router, tags=["video-composer"])
api_router.include_router(asset_router, tags=["asset"])
api_router.include_router(story_router, tags=["story"])
api_router.include_router(hook_router, tags=["hook"])
api_router.include_router(content_strategy_router, tags=["content-strategy"])
api_router.include_router(content_idea_generation.router, tags=["content-idea-generation"])
api_router.include_router(content_batch_generate.router, tags=["content-batch"])
api_router.include_router(beat_router, tags=["beat"])
api_router.include_router(series_router, tags=["series"])
api_router.include_router(series_project.router, tags=["series-project"])
api_router.include_router(composition_render.router, tags=["composition-render"])
api_router.include_router(beat_generate.router, tags=["beat-generate"])
api_router.include_router(beat_preview.router, tags=["beat-preview"])
api_router.include_router(batch_router, tags=["batch"])
api_router.include_router(batch_render.router, tags=["batch-render"])
api_router.include_router(quality_gate.router, tags=["quality-gate"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(produced_videos.router, tags=["produced-videos"])
api_router.include_router(factory_pipeline.router, tags=["factory-pipeline"])
api_router.include_router(content_generate.router, tags=["content-generate"])
api_router.include_router(voice_generate.router, tags=["voice-generate"])
api_router.include_router(motion_generate.router, tags=["motion-generate"])
api_router.include_router(audio_generate.router, tags=["audio-generate"])
api_router.include_router(caption_generate.router, tags=["caption-generate"])
api_router.include_router(package_generate.router, tags=["package-generate"])
api_router.include_router(final_qa.router, tags=["final-qa"])
