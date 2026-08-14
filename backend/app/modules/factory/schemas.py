"""Pure Pydantic contracts for FactoryRun -- see models.py's docstring for
why this module has no cross-module imports.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.modules.factory.models import FACTORY_MAX_ATTEMPTS, FACTORY_RUN_STATUSES, FACTORY_STAGES

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

# Task 19 (see docs/features/45-factory-reliability.md) section 27/28 --
# stable classification for every error_code this module (or a RenderJob it
# handed off to, see app.core.render_errors) can ever set on a FactoryRun.
# Never used to *block* a retry (this app has no automatic retry loop, so
# there is no "automatic limit" to enforce -- see FACTORY_MAX_ATTEMPTS'
# own docstring); purely so the frontend can phrase Retry correctly
# ("try again" vs "fix this first, then retry").
TRANSIENT = "TRANSIENT"
PERMANENT = "PERMANENT"
USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"

ERROR_CLASSIFICATION: dict[str, str] = {
    # This module's own codes.
    BEAT_GENERATION_FAILED: TRANSIENT,  # usually an AI-provider timeout/error; a missing script is the rarer case
    INVALID_EXISTING_BEAT_PLAN: USER_ACTION_REQUIRED,
    ASSET_MATCH_FAILED: USER_ACTION_REQUIRED,
    QUALITY_BLOCKED: USER_ACTION_REQUIRED,
    RENDER_FAILED: TRANSIENT,
    FACTORY_INTERRUPTED: TRANSIENT,
    FACTORY_ALREADY_RUNNING: PERMANENT,
    PROJECT_NOT_FOUND: PERMANENT,
    NOT_RESUMABLE: PERMANENT,
    "UNEXPECTED_ERROR": PERMANENT,
    # app.core.render_errors codes -- a RENDERING-stage failure passes one
    # of these straight through onto FactoryRun.error_code (see
    # factory_pipeline.py's reconcile_factory_runs_on_startup/
    # _on_render_job_failed), never re-mapped, so this module classifies
    # them too rather than leaving a render failure unclassified.
    # ("PROJECT_NOT_FOUND" is shared verbatim with this module's own code
    # above, already covered.)
    "INVALID_BEAT_PLAN": USER_ACTION_REQUIRED,
    "MISSING_ASSET": USER_ACTION_REQUIRED,
    "INVALID_MOTION": USER_ACTION_REQUIRED,
    "MISSING_AUDIO": USER_ACTION_REQUIRED,
    "INVALID_CAPTION_CONFIG": USER_ACTION_REQUIRED,
    "FFMPEG_NOT_FOUND": PERMANENT,
    "FFPROBE_NOT_FOUND": PERMANENT,
    "OUTPUT_DIR_NOT_WRITABLE": USER_ACTION_REQUIRED,
    "OUTPUT_VALIDATION_FAILED": TRANSIENT,
    "CAPTION_RENDER_FAILED": TRANSIENT,
    "AUDIO_RENDER_FAILED": TRANSIENT,
    "INSUFFICIENT_DISK_SPACE": USER_ACTION_REQUIRED,
    "RENDER_INTERRUPTED": TRANSIENT,
}


def classify_error(error_code: str | None) -> str | None:
    """An error_code this map has never seen (a bug, or a brand-new code
    added elsewhere without updating this table) classifies as PERMANENT --
    the conservative default that never implies "just retry, it'll work."
    """
    if error_code is None:
        return None
    return ERROR_CLASSIFICATION.get(error_code, PERMANENT)


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
    attempt: int = 1
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def error_classification(self) -> str | None:
        return classify_error(self.error_code)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_attempts_reached(self) -> bool:
        return self.attempt >= FACTORY_MAX_ATTEMPTS


class FactoryCheckpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    factory_run_id: int
    stage: str
    status: str
    attempt: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    checkpoint_metadata: dict | None = None
    updated_at: datetime


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
