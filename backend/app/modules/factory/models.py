"""FactoryRun (Task 18 -- see docs/features/44-one-click-factory-pipeline.md):
one persistent, recoverable "produce this project" run. Its own table, no
FK into app.modules.beat/video_composer -- `project_id`/`render_job_id`
are bare, unconstrained ints, the same "cross-module reference without a
real FK" convention already used throughout this codebase
(app.modules.batch.models.BatchItem.project_id/render_job_id,
app.modules.beat.models.Project.render_job_id, etc). Per
app/modules/README.md, this module must never import app.modules.beat,
app.modules.asset, app.modules.quality, or app.modules.video_composer --
the composition root (app/api/v1/endpoints/factory_pipeline.py) is the
only place allowed to import all of them together.

`status` mirrors app.modules.video_composer.models.VideoComposeJob's own
COARSE_STATUS/RENDER_PHASE split (Task 11): here, `status` holds the full
granular stage value directly (a FactoryRun's "coarse status" and "current
stage" are the same thing while it's actively progressing -- there is no
useful distinction), and `failed_stage` remembers which stage was active
at the moment a run became FAILED (needed so Retry resumes from the right
stage instead of restarting from PREPARING every time).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# The 13 states from Task 18 section 5, no more. DRAFT is never actually
# persisted (a FactoryRun row is only ever created at the moment
# run_project() starts it -- see factory_pipeline.py), kept in the tuple
# only because the brief lists it as part of the contract and a caller
# may reasonably check `status in FACTORY_RUN_STATUSES`.
FACTORY_RUN_STATUSES = (
    "DRAFT",
    "PREPARING",
    "GENERATING_BEATS",
    "PREPARING_VISUALS",
    "ASSIGNING_ASSETS",
    "QUALITY_CHECK",
    "NEEDS_REVIEW",
    "READY_TO_RENDER",
    "QUEUED",
    "RENDERING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
)

# Stages a run can be "stuck at" when it fails or gets cancelled -- used
# for failed_stage/Retry-resume-point bookkeeping. Excludes the terminal
# statuses themselves (COMPLETED/FAILED/CANCELLED/NEEDS_REVIEW aren't
# "stages", they're outcomes).
FACTORY_STAGES = (
    "PREPARING",
    "GENERATING_BEATS",
    "PREPARING_VISUALS",
    "ASSIGNING_ASSETS",
    "QUALITY_CHECK",
    "READY_TO_RENDER",
    "QUEUED",
    "RENDERING",
)

# A run in any of these statuses is "still doing something" -- exactly one
# per project is allowed at a time (section 44/45's locking requirement).
FACTORY_RUN_ACTIVE_STATUSES = tuple(s for s in FACTORY_RUN_STATUSES if s not in ("COMPLETED", "FAILED", "CANCELLED"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FactoryRun(Base):
    __tablename__ = "factory_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PREPARING")
    # Only set while status == "FAILED" -- which FACTORY_STAGES value was
    # active when the failure happened (section 24/25: Retry must resume
    # from here, not from the beginning).
    failed_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # Bare int, no FK (see module docstring) -- set once the RENDER stage
    # actually creates a real app.modules.video_composer.VideoComposeJob.
    render_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cached from the last Quality Gate run against this project -- purely
    # for cheap reporting (factory_report.json, GET /factory/runs/{id});
    # never re-derived from this instead of the real, live Quality Gate.
    quality_status: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Section 42 -- a lifetime flag: once a run has ever needed a human
    # (entered NEEDS_REVIEW at least once), this stays true even after
    # Continue succeeds and the run completes. review_reason_count is a
    # snapshot of how many issues were open the *last* time it paused.
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_reason_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Section 40 -- production diagnostics, not analytics. One JSON column
    # (matching the established "JSON column instead of a dozen parallel
    # ones" convention -- see VideoComposeJob.composition_request_json,
    # Project.beat_plan_json) holding named seconds-elapsed floats:
    # {"beat_generation": .., "visual_assignment": .., "quality_check": ..,
    #  "queue_wait": .., "render": .., "total": ..}. Keys are only ever
    # added once that stage has actually run in *this* invocation of
    # run_project() -- a reused BeatPlan means "beat_generation" is simply
    # absent, not zero (zero would falsely claim generation ran instantly).
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
