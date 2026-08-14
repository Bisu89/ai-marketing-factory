"""Production Dashboard (Task 17 -- see docs/features/43-production-dashboard.md):
the read-only composition root that answers "what am I producing / what
needs attention / what's rendering / what finished" in one call. Per
app/modules/README.md, this aggregates across app.modules.batch (Batch/
BatchItem), app.modules.beat (Project), app.modules.asset (AssetService,
needed by the Quality Gate), and app.modules.video_composer (VideoComposeJob)
-- none of those modules may import each other, so this file is the one
place allowed to. Mirrors app/api/v1/endpoints/batch_render.py's own
"composition root aggregates several modules, module list stays pure"
shape, applied to a read-only view instead of an orchestrated action.

Scope: only Projects reachable through a BatchItem are considered --
there is no `GET /projects` list anywhere in this codebase (a Project
created outside a batch is only ever addressed by its own id, see
app/modules/beat/models.py's own docstring), so a global "all projects"
view is not a real, listable thing to aggregate over. The classic
singleton beats.json single-project flow (untouched by this task) is
correspondingly out of scope too -- it has no id/list surface either.

`build_dashboard` is a plain function (not just an HTTP handler), the
same "importable, unit-testable independent of FastAPI" shape already
used by quality_gate.run_quality_check -- this is the "DashboardService"
the brief asks for; it lives here rather than in a new app/modules/dashboard/
because it owns no data of its own (no table, no domain rules), it is
purely a read-side aggregation over other modules' already-existing data,
exactly like this file's own batch_render.py sibling.
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.quality_gate import run_quality_check
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.asset.service import AssetService
from app.modules.batch.models import Batch, BatchItem
from app.modules.beat.models import Project
from app.modules.beat.schemas import BeatPlan
from app.modules.quality.schemas import QualityReport
from app.modules.video_composer.models import COARSE_STATUS, VideoComposeJob
from app.modules.video_composer.schemas import job_to_out

router = APIRouter()

_RUNNING_STATUSES = tuple(status for status, coarse in COARSE_STATUS.items() if coarse == "RUNNING")
_PRIORITY_RANK = {"BLOCKED": 0, "FAILED": 1, "NEEDS_REVIEW": 2}
_ATTENTION_LIMIT = 5
_RECENT_LIMIT = 5


# -- Response shapes ---------------------------------------------------


class DashboardSummary(BaseModel):
    ready: int
    needs_review: int
    blocked: int
    rendering: int
    completed_today: int


class DashboardBatchProgress(BaseModel):
    batch_id: int
    name: str
    total: int
    completed: int
    # Only the real, non-zero BatchItemStatus values present in this batch
    # -- never a fabricated 4-bucket split that doesn't match this app's
    # actual 10-status vocabulary (see app.modules.batch.models).
    status_counts: dict[str, int]


class DashboardCurrentRender(BaseModel):
    render_job_id: int
    project_id: int | None
    batch_id: int | None
    project_name: str
    phase: str | None
    progress_current: int | None
    progress_total: int | None
    elapsed_seconds: float


class DashboardAttentionItem(BaseModel):
    batch_id: int
    item_id: int
    project_id: int | None
    project_name: str
    priority: str  # BLOCKED | FAILED | NEEDS_REVIEW
    reason: str


class DashboardVideo(BaseModel):
    render_job_id: int
    project_id: int | None
    batch_id: int | None
    title: str
    status: str  # COMPLETED | FAILED
    duration_sec: float | None
    render_time_seconds: float | None
    output_media_url: str | None
    error_message: str | None = None


class DashboardQueueEntry(BaseModel):
    render_job_id: int
    project_id: int | None
    title: str
    job_status: str  # RUNNING | QUEUED


class DashboardPipeline(BaseModel):
    total_items: int
    status_counts: dict[str, int]


class DashboardCost(BaseModel):
    videos_rendered_today: int
    # This pipeline (motion + composition + ffmpeg, see app.modules.motion/
    # app.modules.composition) has no external video-generation API
    # integration at all -- always real zeros, not computed from data.
    # Distinct from AI *content* generation (Beat text via Claude), which
    # this dashboard deliberately does not report: Beat generation isn't
    # recorded in app.modules.ai.history.AIGenerationHistory (that table
    # requires a Library `video_id`, which Beat/Project rows don't have),
    # so there is no real timestamped source to compute "today's AI calls"
    # from -- reporting a guess would violate this task's own "no invented
    # metrics" rule.
    external_video_api_calls: int = 0
    external_video_api_cost: float = 0.0


class DashboardOut(BaseModel):
    has_any_data: bool
    summary: DashboardSummary
    current_batch: DashboardBatchProgress | None
    current_render: DashboardCurrentRender | None
    attention: list[DashboardAttentionItem]
    attention_total: int
    recent_videos: list[DashboardVideo]
    recent_failures: list[DashboardVideo]
    queue: list[DashboardQueueEntry]
    pipeline: DashboardPipeline
    cost: DashboardCost


# -- Aggregation ---------------------------------------------------------


def _is_batch_active(batch: Batch) -> bool:
    # Mirrors frontend/src/pages/BatchDetailPage.tsx's own isActive() --
    # batch.status is only recomputed by actions (render/sync/retry/...),
    # never by this read-only endpoint (section 23: must not modify
    # state), so a RENDERING item is checked directly rather than trusting
    # a possibly-stale batch.status alone.
    return batch.status == "PROCESSING" or any(item.status == "RENDERING" for item in batch.items)


def _project_title(project: Project | None, fallback: str) -> str:
    return project.name if project is not None else fallback


def _as_utc(dt: datetime) -> datetime:
    # SQLite doesn't actually persist tzinfo on a DateTime(timezone=True)
    # column -- a value round-tripped through the DB comes back naive even
    # though every write path (see _utcnow() helpers across this codebase)
    # always writes real UTC. Without this, subtracting a DB-loaded
    # timestamp from datetime.now(timezone.utc) raises TypeError.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def build_dashboard(db: Session, settings: Settings) -> DashboardOut:
    library_dir = Path(settings.library_dir)

    batches = db.query(Batch).options(selectinload(Batch.items)).order_by(Batch.created_at.desc()).all()
    all_items: list[tuple[Batch, BatchItem]] = [(batch, item) for batch in batches for item in batch.items]

    has_any_data = bool(batches) or db.query(VideoComposeJob.id).first() is not None

    project_ids = {item.project_id for _, item in all_items if item.project_id is not None}
    projects = db.query(Project).filter(Project.id.in_(project_ids)).all() if project_ids else []
    project_by_id: dict[int, Project] = {project.id: project for project in projects}

    item_by_render_job_id: dict[int, tuple[Batch, BatchItem]] = {
        item.render_job_id: (batch, item) for batch, item in all_items if item.render_job_id is not None
    }

    # -- Quality Gate pass: only items that could plausibly render right
    # now (BEATS_READY) or are sitting on a past review verdict that may
    # have since been fixed (NEEDS_REVIEW) -- same scope as
    # batch_render.check_batch_quality, never the full historical set. --
    asset_service = AssetService(db)
    quality_by_item_id: dict[int, QualityReport] = {}
    for _, item in all_items:
        if item.status not in ("BEATS_READY", "NEEDS_REVIEW"):
            continue
        project = project_by_id.get(item.project_id) if item.project_id is not None else None
        if project is None:
            continue
        try:
            plan = BeatPlan.model_validate(project.beat_plan_json)
        except Exception:
            continue
        quality_by_item_id[item.id] = run_quality_check(plan.beats, plan.config, asset_service)

    ready = sum(1 for report in quality_by_item_id.values() if report.status == "READY")
    needs_review = sum(1 for report in quality_by_item_id.values() if report.status == "NEEDS_REVIEW")
    blocked = sum(1 for report in quality_by_item_id.values() if report.status == "BLOCKED")
    blocked += sum(1 for _, item in all_items if item.status == "SKIPPED")

    # -- RenderJob aggregates (own queries, not derived from batch items --
    # a VideoComposeJob can exist without any batch, e.g. the classic
    # single-project flow) --
    rendering_count = db.query(VideoComposeJob).filter(VideoComposeJob.status.in_(_RUNNING_STATUSES)).count()
    running_job = (
        db.query(VideoComposeJob)
        .filter(VideoComposeJob.status.in_(_RUNNING_STATUSES))
        .order_by(VideoComposeJob.created_at.desc())
        .first()
    )
    queued_jobs = (
        db.query(VideoComposeJob).filter(VideoComposeJob.status == "queued").order_by(VideoComposeJob.created_at.asc()).all()
    )
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = (
        db.query(VideoComposeJob)
        .filter(VideoComposeJob.status == "completed", VideoComposeJob.completed_at >= today_start)
        .count()
    )
    recent_completed_jobs = (
        db.query(VideoComposeJob)
        .filter(VideoComposeJob.status == "completed")
        .order_by(VideoComposeJob.completed_at.desc())
        .limit(_RECENT_LIMIT)
        .all()
    )
    recent_failed_jobs = (
        db.query(VideoComposeJob)
        .filter(VideoComposeJob.status == "failed")
        .order_by(VideoComposeJob.completed_at.desc())
        .limit(_RECENT_LIMIT)
        .all()
    )

    summary = DashboardSummary(
        ready=ready, needs_review=needs_review, blocked=blocked,
        rendering=rendering_count, completed_today=completed_today,
    )

    # -- Current batch (section 6) --
    active_batches = [batch for batch in batches if _is_batch_active(batch)]
    current_batch = None
    if active_batches:
        batch = active_batches[0]  # already ordered by created_at desc
        status_counts: dict[str, int] = {}
        for item in batch.items:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
        current_batch = DashboardBatchProgress(
            batch_id=batch.id, name=batch.name, total=len(batch.items),
            completed=status_counts.get("COMPLETED", 0), status_counts=status_counts,
        )

    # -- Current render + queue (sections 8, 13) --
    current_render = None
    queue: list[DashboardQueueEntry] = []
    if running_job is not None:
        match = item_by_render_job_id.get(running_job.id)
        project = project_by_id.get(match[1].project_id) if match and match[1].project_id else None
        out = job_to_out(running_job, library_dir)
        current_render = DashboardCurrentRender(
            render_job_id=running_job.id,
            project_id=match[1].project_id if match else None,
            batch_id=match[0].id if match else None,
            project_name=_project_title(project, running_job.title),
            phase=out.phase,
            progress_current=out.progress_current,
            progress_total=out.progress_total,
            elapsed_seconds=(datetime.now(timezone.utc) - _as_utc(running_job.created_at)).total_seconds(),
        )
        queue.append(
            DashboardQueueEntry(
                render_job_id=running_job.id, project_id=match[1].project_id if match else None,
                title=_project_title(project, running_job.title), job_status="RUNNING",
            )
        )
    for job in queued_jobs:
        match = item_by_render_job_id.get(job.id)
        project = project_by_id.get(match[1].project_id) if match and match[1].project_id else None
        queue.append(
            DashboardQueueEntry(
                render_job_id=job.id, project_id=match[1].project_id if match else None,
                title=_project_title(project, job.title), job_status="QUEUED",
            )
        )

    # -- Needs Attention (sections 9-10) --
    attention_candidates: list[tuple[int, datetime, DashboardAttentionItem]] = []
    for batch, item in all_items:
        project = project_by_id.get(item.project_id) if item.project_id is not None else None
        project_name = _project_title(project, f"Item {item.index:03d}")

        if item.status == "SKIPPED":
            priority = "BLOCKED"
            reason = item.error_message or "Blocked -- see project for details."
        elif item.status == "FAILED":
            priority = "FAILED"
            reason = item.error_message or "Render failed."
        elif item.id in quality_by_item_id and quality_by_item_id[item.id].status == "BLOCKED":
            report = quality_by_item_id[item.id]
            priority = "BLOCKED"
            reason = report.issues[0].message if report.issues else "Blocked by Quality Gate."
        elif item.id in quality_by_item_id and quality_by_item_id[item.id].status == "NEEDS_REVIEW":
            report = quality_by_item_id[item.id]
            priority = "NEEDS_REVIEW"
            reason = report.warnings[0].message if report.warnings else "Needs review."
        else:
            continue

        entry = DashboardAttentionItem(
            batch_id=batch.id, item_id=item.id, project_id=item.project_id,
            project_name=project_name, priority=priority, reason=reason,
        )
        attention_candidates.append((_PRIORITY_RANK[priority], batch.created_at, entry))

    attention_candidates.sort(key=lambda t: (t[0], -t[1].timestamp()))
    attention_total = len(attention_candidates)
    attention = [entry for _, _, entry in attention_candidates[:_ATTENTION_LIMIT]]

    # -- Recent videos / failures (sections 11-12) --
    def _to_video(job: VideoComposeJob, status_label: str) -> DashboardVideo:
        match = item_by_render_job_id.get(job.id)
        project = project_by_id.get(match[1].project_id) if match and match[1].project_id else None
        out = job_to_out(job, library_dir)
        return DashboardVideo(
            render_job_id=job.id, project_id=match[1].project_id if match else None,
            batch_id=match[0].id if match else None, title=_project_title(project, job.title),
            status=status_label, duration_sec=out.render_duration_sec,
            render_time_seconds=out.render_time_seconds, output_media_url=out.output_media_url,
            error_message=job.error_message,
        )

    recent_videos = [_to_video(job, "COMPLETED") for job in recent_completed_jobs]
    recent_failures = [_to_video(job, "FAILED") for job in recent_failed_jobs]

    # -- Production pipeline (section 18) -- real status counts, not an
    # invented per-stage ready/review split this codebase's real states
    # don't actually distinguish (Quality Gate is the one review point for
    # everything -- visuals/motion/audio/pacing/etc together, not staged). --
    pipeline_counts: dict[str, int] = {}
    for _, item in all_items:
        pipeline_counts[item.status] = pipeline_counts.get(item.status, 0) + 1
    pipeline = DashboardPipeline(total_items=len(all_items), status_counts=pipeline_counts)

    cost = DashboardCost(videos_rendered_today=completed_today)

    return DashboardOut(
        has_any_data=has_any_data, summary=summary, current_batch=current_batch,
        current_render=current_render, attention=attention, attention_total=attention_total,
        recent_videos=recent_videos, recent_failures=recent_failures, queue=queue,
        pipeline=pipeline, cost=cost,
    )


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> DashboardOut:
    return build_dashboard(db, settings)
