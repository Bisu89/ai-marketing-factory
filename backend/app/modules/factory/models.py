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

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
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
    # Task 21 (see docs/features/47-content-brief-script-engine.md) --
    # Idea -> ContentBrief -> Script, ahead of Beat generation. A real,
    # instantaneous no-op when the project already has a script (the exact
    # same "reuse, don't regenerate" idempotency GENERATING_BEATS already
    # established for beats -- see factory_pipeline.py's
    # _stage_generate_content).
    "PREPARING_CONTENT",
    "GENERATING_BEATS",
    "PREPARING_VISUALS",
    "ASSIGNING_ASSETS",
    "GENERATING_VOICE",
    # Task 23 (see docs/features/49-local-motion-engine.md) -- turns each
    # Beat's assigned visual Asset into a real, cached, independently-
    # retryable animated clip (FFmpeg Ken-Burns for images, trim/scale/crop
    # for existing video) ahead of Quality/Render. Placed *after*
    # GENERATING_VOICE, not before it as this task's own brief originally
    # sketched (VISUAL -> MOTION -> VOICE) -- a real dependency discovered
    # during this task's own verification: Voice recomputes each Beat's
    # `duration` from real, measured narration timing (see
    # voice_generate.py's generate_project_narration), which would silently
    # invalidate -- wrong duration, failed ffprobe validation -- any Motion
    # clip already rendered against the *original*, pre-Voice duration
    # guess. Motion needs the Beat timing Voice produces to be final before
    # it renders, exactly the "strong dependency reason to reorder" this
    # task's own brief explicitly allows for.
    "GENERATING_MOTION",
    # Task 24 (see docs/features/50-audio-master.md) -- mixes narration
    # (Task 22) with optional local BGM, ducked under narration via ffmpeg
    # sidechaincompress, into one real, cached `audio_master.wav`. Depends
    # only on Voice's own narration.wav (not on Motion, which runs
    # immediately before this) -- placed last among the local-artifact
    # stages, right before Quality, matching this task's own target
    # pipeline order (VOICE -> AUDIO -> QUALITY -> RENDER).
    "GENERATING_AUDIO",
    # Task 25 (see docs/features/51-caption-engine.md) -- turns each Beat's
    # own final narration text + Voice-settled start/end timing into a
    # real, cached `captions.ass`, no ASR/AI caption API. Depends only on
    # Voice's own per-beat start/end (not on Motion or Audio, both
    # independent) -- placed last among the local-artifact stages, right
    # before Quality, matching this task's own target pipeline order
    # (VOICE -> AUDIO -> CAPTIONS -> QUALITY -> RENDER).
    "GENERATING_CAPTIONS",
    "QUALITY_CHECK",
    "NEEDS_REVIEW",
    "READY_TO_RENDER",
    "QUEUED",
    "RENDERING",
    # Task 27 (see docs/features/53-thumbnail-metadata-package.md) --
    # final.mp4 (Task 26) -> thumbnail.jpg + metadata.json, entirely local
    # (frame extraction/scoring + deterministic title/description/hashtag
    # templates, no AI image generation, no LLM call). Runs only after a
    # real, completed render exists -- placed immediately after RENDERING,
    # right before COMPLETED, matching this task's own target pipeline
    # order (RENDER -> PACKAGE -> QA/COMPLETED).
    "PACKAGING",
    # Task 28 (see docs/features/54-final-qa.md) -- a read-only safety net
    # over the finished package (video/audio/thumbnail/metadata/captions
    # integrity + cross-artifact freshness) before a run is ever allowed
    # to reach COMPLETED. A FAIL pauses the run at NEEDS_REVIEW (with
    # failed_stage="FINAL_QA" -- section 76's own explicit "FAIL,
    # NEEDS_REVIEW, repair_stage" test spec), never silently completing on
    # a broken package; PASS/PASS_WITH_WARNINGS both proceed to COMPLETED
    # (section 5: only a hard FAIL blocks readiness).
    "FINAL_QA",
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
    "PREPARING_CONTENT",
    "GENERATING_BEATS",
    "PREPARING_VISUALS",
    "ASSIGNING_ASSETS",
    "GENERATING_VOICE",
    "GENERATING_MOTION",
    "GENERATING_AUDIO",
    "GENERATING_CAPTIONS",
    "QUALITY_CHECK",
    "READY_TO_RENDER",
    "QUEUED",
    "RENDERING",
    "PACKAGING",
    "FINAL_QA",
)

# A run in any of these statuses is "still doing something" -- exactly one
# per project is allowed at a time (section 44/45's locking requirement).
FACTORY_RUN_ACTIVE_STATUSES = tuple(s for s in FACTORY_RUN_STATUSES if s not in ("COMPLETED", "FAILED", "CANCELLED"))

# Task 19 (see docs/features/45-factory-reliability.md) section 26 -- purely
# informational: this app has no automatic retry loop (every retry is a
# user-triggered POST /factory-runs/{id}/retry -- see factory_pipeline.py),
# so attempts are never blocked past this number. It only flags
# FactoryRunOut.max_attempts_reached so the frontend can show a softer
# "this keeps failing" hint instead of a plain Retry button.
FACTORY_MAX_ATTEMPTS = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FactoryRun(Base):
    __tablename__ = "factory_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Indexed (Task 19 section 43) -- reconcile_factory_runs_on_startup and
    # list_active_runs both filter by status on every startup.
    status: Mapped[str] = mapped_column(String, nullable=False, default="PREPARING", index=True)
    # Only set while status == "FAILED" -- which FACTORY_STAGES value was
    # active when the failure happened (section 24/25: Retry must resume
    # from here, not from the beginning).
    failed_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # Task 19 section 26 -- how many times this run has been (re)started via
    # retry_run(), including the original attempt (so a fresh run is 1, not
    # 0). Never reset by Continue (NEEDS_REVIEW -> QUALITY_CHECK isn't a
    # retry, it's the first real attempt at that stage), only by retry_run.
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Bare int, no FK (see module docstring) -- set once the RENDER stage
    # actually creates a real app.modules.video_composer.VideoComposeJob.
    render_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cached from the last Quality Gate run against this project -- purely
    # for cheap reporting (factory_report.json, GET /factory/runs/{id});
    # never re-derived from this instead of the real, live Quality Gate.
    quality_status: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Task 28 (see docs/features/54-final-qa.md) -- same "cached from the
    # last real run, purely for cheap reporting" shape as quality_status/
    # quality_score above, deliberately a *separate* pair of columns
    # rather than reusing those: this is the POST-render Final QA outcome
    # (PASS/PASS_WITH_WARNINGS/FAIL), a genuinely different check than the
    # PRE-render Quality Gate's own READY/NEEDS_REVIEW/BLOCKED -- reusing
    # the same columns would silently overwrite one project-readiness
    # signal with an unrelated one.
    qa_status: Mapped[str | None] = mapped_column(String, nullable=True)
    qa_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Task 59 (see docs/features/59-ai-image-generation.md) -- only ever
    # populated when this run's project used visual_generation.mode ==
    # "ai_generated"; stays NULL for the default "library" mode (same
    # "meaningfully absent, not zero" convention as qa_status/qa_score
    # above), so a $0 "library" run never falsely reports a $0.00 AI cost.
    visual_generation_image_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_generation_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

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
    # This IS the "last_checkpoint_at"/heartbeat field the Task 19 brief
    # describes (section 5/19/20) -- it already updates on every single
    # stage transition (every set_run_fields() call), so a second, duplicate
    # column would carry the exact same information (see that section's own
    # "if equivalent fields already exist: reuse them" instruction).
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, index=True)


# -- Task 19: per-stage checkpoints (see docs/features/45-factory-reliability.md) --

CHECKPOINT_PENDING = "PENDING"
CHECKPOINT_RUNNING = "RUNNING"
CHECKPOINT_COMPLETED = "COMPLETED"
CHECKPOINT_FAILED = "FAILED"
CHECKPOINT_SKIPPED = "SKIPPED"

FACTORY_CHECKPOINT_STATUSES = (
    CHECKPOINT_PENDING, CHECKPOINT_RUNNING, CHECKPOINT_COMPLETED, CHECKPOINT_FAILED, CHECKPOINT_SKIPPED,
)


class FactoryCheckpoint(Base):
    """A durable, per-(run, stage) audit record answering "what has
    definitely completed" (section 8) independently of FactoryRun.status,
    which only ever holds the *current* stage. A real FK to factory_run.id
    is used here (unlike FactoryRun's own cross-*module* references) since
    both tables live in this same module -- see app/modules/README.md.

    One row per (factory_run_id, stage): start_checkpoint() creates it on
    first entry and re-enters (bumping `attempt`, resetting timestamps) on
    every retry of that same stage, rather than appending a new row per
    attempt -- a run's own checkpoint history is small and stage-keyed by
    nature (PREPARING/GENERATING_BEATS/.../RENDERING, see FACTORY_STAGES),
    and "how many attempts has stage X had" is exactly `attempt` on its one
    row, not something that needs a second query to derive.
    """

    __tablename__ = "factory_checkpoint"

    id: Mapped[int] = mapped_column(primary_key=True)
    factory_run_id: Mapped[int] = mapped_column(ForeignKey("factory_run.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=CHECKPOINT_PENDING)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # Small, non-sensitive stage facts only (e.g. {"beats_generated": true,
    # "beat_count": 5} or {"assigned_count": 2, "auto_assigned": 1}) --
    # never a full BeatPlan/thumbnail/log (section 44/46: no large payloads,
    # no secrets, in SQLite).
    checkpoint_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


assert set(FACTORY_CHECKPOINT_STATUSES) == {"PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"}
