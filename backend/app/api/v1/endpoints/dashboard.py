"""Production Dashboard (Task 17 -- see docs/features/43-production-dashboard.md):
the read-only composition root that answers "what am I producing / what
needs attention / what's rendering / what finished" in one call. Per
app/modules/README.md, this aggregates across app.modules.beat (Project),
app.modules.factory (FactoryRun), app.modules.asset (AssetService, needed
by the Quality Gate), and app.modules.video_composer (VideoComposeJob) --
none of those modules may import each other, so this file is the one place
allowed to.

Scope: every Project, judged by its latest FactoryRun. Batches used to be
the unit this view aggregated over; they were removed (see
docs/features/157-remove-unused-features.md), so a Project is now the unit.

`build_dashboard` is a plain function (not just an HTTP handler), the
same "importable, unit-testable independent of FastAPI" shape already
used by quality_gate.run_quality_check -- it owns no data of its own (no
table, no domain rules), it is purely a read-side aggregation over other
modules' already-existing data.
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.quality_gate import run_quality_check
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.asset.service import AssetService
from app.modules.beat.models import Project
from app.modules.beat.schemas import BeatPlan
from app.modules.factory.models import FactoryRun
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


class DashboardCurrentRender(BaseModel):
    render_job_id: int
    project_id: int | None
    project_name: str
    phase: str | None
    progress_current: int | None
    progress_total: int | None
    elapsed_seconds: float


class DashboardAttentionItem(BaseModel):
    project_id: int
    project_name: str
    priority: str  # BLOCKED | FAILED | NEEDS_REVIEW
    reason: str


class DashboardVideo(BaseModel):
    render_job_id: int
    project_id: int | None
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
    current_render: DashboardCurrentRender | None
    attention: list[DashboardAttentionItem]
    attention_total: int
    recent_videos: list[DashboardVideo]
    recent_failures: list[DashboardVideo]
    queue: list[DashboardQueueEntry]
    pipeline: DashboardPipeline
    cost: DashboardCost


# -- Aggregation ---------------------------------------------------------


def _project_title(project: Project | None, fallback: str) -> str:
    return project.name if project is not None else fallback


def _as_utc(dt: datetime) -> datetime:
    # SQLite doesn't actually persist tzinfo on a DateTime(timezone=True)
    # column -- a value round-tripped through the DB comes back naive even
    # though every write path (see _utcnow() helpers across this codebase)
    # always writes real UTC. Without this, subtracting a DB-loaded
    # timestamp from datetime.now(timezone.utc) raises TypeError.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _latest_run_by_project(db: Session) -> dict[int, FactoryRun]:
    latest: dict[int, FactoryRun] = {}
    for run in db.query(FactoryRun).order_by(FactoryRun.id.asc()).all():
        latest[run.project_id] = run
    return latest


def build_dashboard(db: Session, settings: Settings) -> DashboardOut:
    library_dir = Path(settings.library_dir)

    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    project_by_id: dict[int, Project] = {project.id: project for project in projects}
    latest_run = _latest_run_by_project(db)

    has_any_data = bool(projects) or db.query(VideoComposeJob.id).first() is not None

    # A render job belongs to a project either via Project.render_job_id
    # (its latest render) or via any FactoryRun that started one.
    project_by_render_job_id: dict[int, Project] = {
        project.render_job_id: project for project in projects if project.render_job_id is not None
    }
    for run in db.query(FactoryRun).filter(FactoryRun.render_job_id.isnot(None)).all():
        project = project_by_id.get(run.project_id)
        if project is not None:
            project_by_render_job_id.setdefault(run.render_job_id, project)

    # -- Quality Gate pass: only projects that could plausibly render right
    # now (never rendered, no run started yet) or are sitting on a past
    # review verdict that may have since been fixed (NEEDS_REVIEW) -- never
    # the full historical set. --
    asset_service = AssetService(db)
    quality_by_project_id: dict[int, QualityReport] = {}
    for project in projects:
        run = latest_run.get(project.id)
        awaiting_render = run is None and project.render_job_id is None
        if not (awaiting_render or (run is not None and run.status == "NEEDS_REVIEW")):
            continue
        try:
            plan = BeatPlan.model_validate(project.beat_plan_json)
        except Exception:
            continue
        quality_by_project_id[project.id] = run_quality_check(plan.beats, plan.config, asset_service)

    ready = sum(1 for report in quality_by_project_id.values() if report.status == "READY")
    needs_review = sum(1 for report in quality_by_project_id.values() if report.status == "NEEDS_REVIEW")
    blocked = sum(1 for report in quality_by_project_id.values() if report.status == "BLOCKED")

    # -- RenderJob aggregates (own queries -- a VideoComposeJob can exist
    # without any project, e.g. a plain Video Composer job) --
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

    # -- Current render + queue (sections 8, 13) --
    current_render = None
    queue: list[DashboardQueueEntry] = []
    if running_job is not None:
        project = project_by_render_job_id.get(running_job.id)
        out = job_to_out(running_job, library_dir)
        current_render = DashboardCurrentRender(
            render_job_id=running_job.id,
            project_id=project.id if project else None,
            project_name=_project_title(project, running_job.title),
            phase=out.phase,
            progress_current=out.progress_current,
            progress_total=out.progress_total,
            elapsed_seconds=(datetime.now(timezone.utc) - _as_utc(running_job.created_at)).total_seconds(),
        )
        queue.append(
            DashboardQueueEntry(
                render_job_id=running_job.id, project_id=project.id if project else None,
                title=_project_title(project, running_job.title), job_status="RUNNING",
            )
        )
    for job in queued_jobs:
        project = project_by_render_job_id.get(job.id)
        queue.append(
            DashboardQueueEntry(
                render_job_id=job.id, project_id=project.id if project else None,
                title=_project_title(project, job.title), job_status="QUEUED",
            )
        )

    # -- Needs Attention (sections 9-10) --
    attention_candidates: list[tuple[int, datetime, DashboardAttentionItem]] = []
    for project in projects:
        run = latest_run.get(project.id)
        report = quality_by_project_id.get(project.id)
        if run is not None and run.status == "FAILED":
            priority = "FAILED"
            reason = run.error_message or "Production failed."
        elif report is not None and report.status == "BLOCKED":
            priority = "BLOCKED"
            reason = report.issues[0].message if report.issues else "Blocked by Quality Gate."
        elif report is not None and report.status == "NEEDS_REVIEW":
            priority = "NEEDS_REVIEW"
            reason = report.warnings[0].message if report.warnings else "Needs review."
        else:
            continue

        entry = DashboardAttentionItem(
            project_id=project.id, project_name=project.name, priority=priority, reason=reason,
        )
        attention_candidates.append((_PRIORITY_RANK[priority], _as_utc(project.created_at), entry))

    attention_candidates.sort(key=lambda t: (t[0], -t[1].timestamp()))
    attention_total = len(attention_candidates)
    attention = [entry for _, _, entry in attention_candidates[:_ATTENTION_LIMIT]]

    # -- Recent videos / failures (sections 11-12) --
    def _to_video(job: VideoComposeJob, status_label: str) -> DashboardVideo:
        project = project_by_render_job_id.get(job.id)
        out = job_to_out(job, library_dir)
        return DashboardVideo(
            render_job_id=job.id, project_id=project.id if project else None,
            title=_project_title(project, job.title),
            status=status_label, duration_sec=out.render_duration_sec,
            render_time_seconds=out.render_time_seconds, output_media_url=out.output_media_url,
            error_message=job.error_message,
        )

    recent_videos = [_to_video(job, "COMPLETED") for job in recent_completed_jobs]
    recent_failures = [_to_video(job, "FAILED") for job in recent_failed_jobs]

    # -- Production pipeline (section 18) -- real status counts of each
    # project's latest FactoryRun, not an invented per-stage split. --
    pipeline_counts: dict[str, int] = {}
    for run in latest_run.values():
        pipeline_counts[run.status] = pipeline_counts.get(run.status, 0) + 1
    pipeline = DashboardPipeline(total_items=len(latest_run), status_counts=pipeline_counts)

    cost = DashboardCost(videos_rendered_today=completed_today)

    return DashboardOut(
        has_any_data=has_any_data, summary=summary,
        current_render=current_render, attention=attention, attention_total=attention_total,
        recent_videos=recent_videos, recent_failures=recent_failures, queue=queue,
        pipeline=pipeline, cost=cost,
    )


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> DashboardOut:
    return build_dashboard(db, settings)
