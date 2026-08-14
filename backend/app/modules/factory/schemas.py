"""Pure Pydantic contracts for FactoryRun -- see models.py's docstring for
why this module has no cross-module imports.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.factory.models import FACTORY_RUN_STATUSES, FACTORY_STAGES

# Factory-specific error codes (Task 18 section 24/53: stable codes, never
# a raw stack trace). Distinct from app.core.render_errors -- those cover
# the render *pipeline's* own internal phases; these cover the factory
# orchestration stages that wrap it. A render-stage failure still carries
# whichever app.core.render_errors code the underlying RenderJob itself
# recorded (see factory_pipeline.py), passed straight through rather than
# re-mapped.
BEAT_GENERATION_FAILED = "BEAT_GENERATION_FAILED"
INVALID_EXISTING_BEAT_PLAN = "INVALID_EXISTING_BEAT_PLAN"
ASSET_MATCH_FAILED = "ASSET_MATCH_FAILED"
QUALITY_BLOCKED = "QUALITY_BLOCKED"
RENDER_FAILED = "RENDER_FAILED"
FACTORY_INTERRUPTED = "FACTORY_INTERRUPTED"
FACTORY_ALREADY_RUNNING = "FACTORY_ALREADY_RUNNING"
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
NOT_RESUMABLE = "NOT_RESUMABLE"


class FactoryRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    status: str
    failed_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    render_job_id: int | None = None
    quality_status: str | None = None
    quality_score: int | None = None
    requires_human_review: bool = False
    review_reason_count: int = 0
    metrics: dict = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class FactoryRunRequest(BaseModel):
    # If a project already has an active (non-terminal) run, run_project()
    # reuses it rather than creating a second one (section 43/44) -- this
    # flag has no effect in that case; it only matters when starting fresh.
    mode: str = "AUTO"  # Section 35 -- exactly MANUAL/AUTO, nothing else.


assert set(FACTORY_RUN_STATUSES) == {
    "DRAFT", "PREPARING", "GENERATING_BEATS", "PREPARING_VISUALS", "ASSIGNING_ASSETS",
    "QUALITY_CHECK", "NEEDS_REVIEW", "READY_TO_RENDER", "QUEUED", "RENDERING",
    "COMPLETED", "FAILED", "CANCELLED",
}
assert set(FACTORY_STAGES) == {
    "PREPARING", "GENERATING_BEATS", "PREPARING_VISUALS", "ASSIGNING_ASSETS",
    "QUALITY_CHECK", "READY_TO_RENDER", "QUEUED", "RENDERING",
}
