"""One-click Factory Pipeline (Task 18 -- see
docs/features/44-one-click-factory-pipeline.md): the orchestration
composition root that connects Script -> Beat -> Visual -> Quality ->
Render using only already-existing services. Per app/modules/README.md,
none of app.modules.factory/beat/asset/quality/batch/video_composer may
import each other; this file is the one place allowed to import all of
them, exactly like app/api/v1/endpoints/batch_render.py already does for
"many projects at once" -- this is that same composition-root pattern
applied to "one project's full pipeline, end to end."

No new render pipeline, queue, quality engine, asset matcher, or Beat
generator is implemented here. Every real unit of work is delegated:

    generate_beat_plan()          <- app/api/v1/endpoints/beat_generate.py
    AssetService.search()         <- app.modules.asset (the closest real
                                      thing to an "AssetMatcher" this
                                      codebase has -- see Task 14/15/16's
                                      own repeated finding that no separate
                                      AssetMatcher/VisualIntent system
                                      exists)
    compute_asset_confidence()    <- app/api/v1/endpoints/quality_gate.py
    run_quality_check()           <- app/api/v1/endpoints/quality_gate.py
    project_composition_plan()    <- app/api/v1/endpoints/batch_render.py
    render_composition()          <- app/api/v1/endpoints/composition_render.py
    VideoComposerService          <- app.modules.video_composer (the one
                                      LocalRenderQueue/RenderWorker)

This file's own job is purely sequencing + state persistence (FactoryRun)
+ translating a stage's success/failure into the next stage or a stable,
user-facing error code.

Threading model: a FactoryRun's local stages (PREPARING through
QUALITY_CHECK) run on a plain daemon background thread (mirroring
app/api/v1/endpoints/batch_render.py's own `_run_batch_beat_generation`
thread) since GENERATING_BEATS may call the real Claude API and must not
block the HTTP request. Once a RenderJob is created, this file's own
thread is done -- QUEUED -> RENDERING -> COMPLETED/FAILED is driven
entirely by VideoComposerService's existing worker + the render.job.*
events it already publishes (see register_factory_event_handlers, wired
once at app startup in app/main.py). There is no persistent "factory
worker process" -- a FactoryRun found in an active status at process
startup can only mean the previous process died mid-run (see
reconcile_factory_runs_on_startup).
"""

import concurrent.futures
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.batch_render import project_composition_plan
from app.api.v1.endpoints.beat_generate import generate_beat_plan
from app.api.v1.endpoints.composition_render import render_composition
from app.api.v1.endpoints.quality_gate import compute_asset_confidence, run_quality_check, tokenize_prose
from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, FileOperationError, NotFoundError, ValidationError
from app.core.events import EventBus
from app.db.session import SessionLocal, get_db
from app.modules.asset.service import AssetService
from app.modules.batch.service import get_batch as get_batch_row
from app.modules.beat.models import Project
from app.modules.beat.project_service import get_project_draft, set_project_render_job_id, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan
from app.modules.factory import service as factory_service
from app.modules.factory.models import FactoryRun
from app.modules.factory.schemas import (
    ASSET_MATCH_FAILED,
    BEAT_GENERATION_FAILED,
    FactoryRunOut,
    INVALID_EXISTING_BEAT_PLAN,
    NOT_RESUMABLE,
    QUALITY_BLOCKED,
    RENDER_FAILED,
)
from app.modules.video_composer.models import VideoComposeJob
from app.modules.video_composer.schemas import job_to_out
from app.modules.video_composer.service import VideoComposerService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_video_composer_service(request: Request) -> VideoComposerService:
    return request.app.state.video_composer_service


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FactoryStageError(Exception):
    """Raised by a stage function to report a real, user-facing failure
    (never a raw stack trace -- section 24/53). Caught once, in
    _execute_pipeline_sync's own try/except, and turned into
    FactoryRun.failed_stage/error_code/error_message.
    """

    def __init__(self, stage: str, code: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.message = message


# -- Per-run cancellation signalling (mirrors VideoComposerService's own
# per-job _cancel_events dict -- a local stage can't be force-killed
# mid-external-API-call, but the background thread checks this between
# every stage boundary, section 22's own "stop safely," not instantly) --

_cancel_events: dict[int, threading.Event] = {}
_cancel_events_lock = threading.Lock()


def _cancel_event_for(run_id: int) -> threading.Event:
    with _cancel_events_lock:
        event = _cancel_events.get(run_id)
        if event is None:
            event = threading.Event()
            _cancel_events[run_id] = event
        return event


def _drop_cancel_event(run_id: int) -> None:
    with _cancel_events_lock:
        _cancel_events.pop(run_id, None)


def _bail_if_cancelled(run_id: int, cancel_event: threading.Event) -> bool:
    if not cancel_event.is_set():
        return False
    factory_service.set_run_fields(run_id, status="CANCELLED", completed_at=_utcnow())
    return True


# -- Stage: GENERATING_BEATS ----------------------------------------------


def _stage_generate_beats(project_id: int, settings: Settings) -> tuple[BeatPlan, bool]:
    """Section 11: an existing, valid BeatPlan is reused untouched; a
    missing one is generated; an existing-but-invalid one FAILs rather
    than silently overwriting whatever the user already has. Returns
    (plan, did_generate) -- did_generate is only True when the AI was
    actually called, so the caller can decide whether "beat_generation"
    belongs in this run's timing metrics at all (see models.py's own
    "missing key, not zero" convention).
    """
    draft = get_project_draft(project_id)

    if draft.beats:
        try:
            plan = BeatPlan(
                script_text=draft.script_text, beats=draft.beats,
                project_name=draft.project_name, config=draft.config,
            )
        except PydanticValidationError as exc:
            raise FactoryStageError(
                "GENERATING_BEATS", INVALID_EXISTING_BEAT_PLAN,
                f"This project's existing beats are invalid and were not regenerated automatically: {exc}",
            ) from exc
        return plan, False

    script = (draft.script_text or "").strip()
    if not script:
        raise FactoryStageError(
            "GENERATING_BEATS", BEAT_GENERATION_FAILED, "This project has no script to generate beats from."
        )

    try:
        generated = generate_beat_plan(settings.anthropic_api_key, script)
    except (ValidationError, ExternalServiceError) as exc:
        raise FactoryStageError("GENERATING_BEATS", BEAT_GENERATION_FAILED, str(exc)) from exc

    plan = BeatPlan(
        script_text=generated.script_text, beats=generated.beats,
        project_name=draft.project_name, config=draft.config,
    )
    update_project_beat_plan(project_id, plan)
    return plan, True


# -- Stage: ASSIGNING_ASSETS -----------------------------------------------


def _auto_assign_visual(beat: Beat, asset_service: AssetService) -> tuple[int | None, str | None]:
    """The factory's own "AssetMatcher" call site (section 13) -- reuses
    AssetService.search() (the closest real matcher this codebase has, see
    module docstring) to find candidates for a beat's visual_hint, then
    quality_gate.compute_asset_confidence() (also reused, not
    reimplemented) to score the top one. Returns (None, None) when there's
    nothing to search with or nothing found -- the caller leaves the beat
    unassigned in that case, and the existing Quality Gate's own
    MISSING_VISUAL_ASSET check picks it up from there (section 12: an
    optional missing visual description never blocks the whole factory by
    itself).
    """
    if not beat.visual_hint:
        return None, None
    tokens = list(tokenize_prose(beat.visual_hint))
    if not tokens:
        return None, None

    candidates = [
        asset for asset in asset_service.search(query=tokens, asset_type="image")
        if asset.effective_status == "ACTIVE"
    ]
    if not candidates:
        return None, None

    top = candidates[0]
    return top.id, compute_asset_confidence(beat, top)


def _stage_assign_assets(plan: BeatPlan, asset_service: AssetService) -> BeatPlan:
    """Section 14: a beat that already has asset_id set (manual OR a
    previous auto-assignment) is never touched again -- MANUAL ASSIGNMENT
    > AUTO ASSIGNMENT > SUGGESTION means this stage only ever *adds*
    assignments, never replaces one. HIGH/MEDIUM/LOW are all assigned on a
    best-effort basis (section 13's own table); which confidence levels
    additionally require human review is a *policy* decision evaluated
    fresh at QUALITY_CHECK time (see _count_beats_needing_policy_review),
    not baked in here, so Continue-after-fix re-evaluates it against
    whatever the user changed rather than a stale snapshot.
    """
    config = plan.config.factory
    updated_beats: list[Beat] = []
    for beat in plan.ordered_beats():
        if beat.asset_id is not None:
            updated_beats.append(beat)
            continue

        asset_id, confidence = _auto_assign_visual(beat, asset_service)
        if asset_id is None:
            updated_beats.append(beat)
            continue

        if confidence == "HIGH" and not config.auto_assign_high_confidence:
            updated_beats.append(beat)
            continue

        updated_beats.append(beat.model_copy(update={"asset_id": asset_id}))

    return plan.model_copy(update={"beats": updated_beats})


def _count_beats_needing_policy_review(plan: BeatPlan, asset_service: AssetService) -> int:
    """Section 36's factory-level review policy, layered *on top of* the
    unmodified Quality Gate (which only ever warns on LOW confidence, see
    app.modules.quality.analyzer.analyze_visual) -- MEDIUM confidence is a
    real, configurable factory policy concern the Quality Gate itself
    deliberately doesn't score as a defect (a medium match isn't wrong,
    just uncertain enough that this app's own default policy wants a human
    to glance at it before render). Recomputed fresh from whichever assets
    are *currently* assigned, not cached from the ASSIGNING_ASSETS stage --
    this is what makes Continue-after-a-manual-fix correct without
    re-running assignment (section 18).
    """
    config = plan.config.factory
    if not (config.require_review_for_medium_confidence or config.require_review_for_low_confidence):
        return 0

    count = 0
    for beat in plan.beats:
        if beat.asset_id is None:
            continue
        try:
            asset = asset_service.get(beat.asset_id)
        except NotFoundError:
            continue
        if asset.effective_status != "ACTIVE":
            continue
        confidence = compute_asset_confidence(beat, asset)
        if confidence == "MEDIUM" and config.require_review_for_medium_confidence:
            count += 1
        elif confidence == "LOW" and config.require_review_for_low_confidence:
            count += 1
    return count


# -- Stage: QUALITY_CHECK + render handoff ---------------------------------


def _run_quality_and_proceed(
    run_id: int, project_id: int, plan: BeatPlan, settings: Settings,
    cancel_event: threading.Event, service: VideoComposerService,
) -> None:
    db = SessionLocal()
    try:
        asset_service = AssetService(db)
        t0 = time.monotonic()
        report = run_quality_check(plan.beats, plan.config, asset_service)
        policy_review_count = _count_beats_needing_policy_review(plan, asset_service)
        factory_service.merge_metrics(run_id, quality_check_seconds=round(time.monotonic() - t0, 3))
    finally:
        db.close()

    factory_service.set_run_fields(run_id, quality_status=report.status, quality_score=report.score)

    if report.status == "BLOCKED":
        first_issue = report.issues[0].message if report.issues else "The Quality Gate blocked this project."
        raise FactoryStageError("QUALITY_CHECK", QUALITY_BLOCKED, first_issue)

    if report.status == "NEEDS_REVIEW" or policy_review_count > 0:
        reason_count = max(len(report.warnings) + policy_review_count, 1)
        factory_service.set_run_fields(
            run_id, status="NEEDS_REVIEW", requires_human_review=True, review_reason_count=reason_count,
        )
        return

    if _bail_if_cancelled(run_id, cancel_event):
        return

    if not plan.config.factory.render_after_quality_pass:
        factory_service.set_run_fields(run_id, status="READY_TO_RENDER")
        return

    _stage_render(run_id, project_id, plan, settings, service)


def _stage_render(
    run_id: int, project_id: int, plan: BeatPlan, settings: Settings, service: VideoComposerService
) -> None:
    """Section 20/21: this function's entire job is "build the plan, hand
    it to the existing render_composition()/LocalRenderQueue, remember the
    job id" -- it never touches FFmpeg, never polls, never blocks waiting
    for the render to finish. QUEUED -> RENDERING -> COMPLETED/FAILED from
    here on is entirely driven by VideoComposerService's own worker thread
    + the render.job.* events it already publishes (see
    register_factory_event_handlers below).
    """
    factory_service.set_run_fields(run_id, status="READY_TO_RENDER")

    db = SessionLocal()
    try:
        asset_service = AssetService(db)
        try:
            composition_plan, asset_paths, narration_asset_paths = project_composition_plan(plan, asset_service)
        except (ValidationError, NotFoundError, FileOperationError) as exc:
            raise FactoryStageError("READY_TO_RENDER", ASSET_MATCH_FAILED, str(exc)) from exc
    finally:
        db.close()

    try:
        job_id = render_composition(
            composition_plan, asset_paths, service,
            title=plan.project_name or f"Project {project_id}",
            narration_asset_paths=narration_asset_paths or None,
            profile=plan.config.render.profile,
            min_free_disk_mb=settings.min_free_disk_mb,
        )
    except (ValidationError, FileOperationError) as exc:
        raise FactoryStageError("QUEUED", RENDER_FAILED, str(exc)) from exc

    set_project_render_job_id(project_id, job_id)
    factory_service.set_run_fields(run_id, status="QUEUED", render_job_id=job_id)


# -- Orchestration entry points --------------------------------------------


def _execute_pipeline_sync(run_id: int, project_id: int, settings: Settings, service: VideoComposerService) -> None:
    """The full blocking pipeline body -- PREPARING through either
    NEEDS_REVIEW, QUEUED (render handed off), READY_TO_RENDER (render
    disabled by policy), or FAILED. Called on its own daemon thread for an
    interactively-triggered run (see create_and_start_run), or directly
    inside a bounded ThreadPoolExecutor worker for a batch-triggered one
    (see run_batch_factory) -- the concurrency bound is the *caller's*
    concern in that case, this function itself has no opinion about it.
    """
    cancel_event = _cancel_event_for(run_id)
    current_stage = "PREPARING"
    try:
        factory_service.set_run_fields(run_id, status="PREPARING")
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "GENERATING_BEATS"
        factory_service.set_run_fields(run_id, status=current_stage)
        t0 = time.monotonic()
        plan, generated = _stage_generate_beats(project_id, settings)
        if generated:
            factory_service.merge_metrics(run_id, beat_generation_seconds=round(time.monotonic() - t0, 3))
        if _bail_if_cancelled(run_id, cancel_event):
            return

        # PREPARING_VISUALS: a pass-through, not a real generation step in
        # this codebase -- beat_generate.py's own Claude call already
        # produces visual_hint for every beat as part of GENERATING_BEATS
        # (see that file's OUTPUT_SCHEMA), and a beat authored/edited by a
        # human may simply have none (Beat.visual_hint is Optional) with no
        # separate AI visual-description generator to fall back to. Either
        # way there is nothing further to *generate* here (section 12's
        # "do not block the factory over an optional missing description")
        # -- ASSIGNING_ASSETS below already treats "no visual_hint" as
        # "leave unassigned, let Quality Gate flag it" on its own.
        current_stage = "PREPARING_VISUALS"
        factory_service.set_run_fields(run_id, status=current_stage)
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "ASSIGNING_ASSETS"
        factory_service.set_run_fields(run_id, status=current_stage)
        t0 = time.monotonic()
        db = SessionLocal()
        try:
            plan = _stage_assign_assets(plan, AssetService(db))
        finally:
            db.close()
        update_project_beat_plan(project_id, plan)
        factory_service.merge_metrics(run_id, visual_assignment_seconds=round(time.monotonic() - t0, 3))
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "QUALITY_CHECK"
        factory_service.set_run_fields(run_id, status=current_stage)
        _run_quality_and_proceed(run_id, project_id, plan, settings, cancel_event, service)
    except FactoryStageError as exc:
        _mark_failed(run_id, exc.stage, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001 -- never a raw stack trace to the user (section 24)
        logger.exception("FactoryRun %s failed unexpectedly at %s", run_id, current_stage)
        _mark_failed(run_id, current_stage, "UNEXPECTED_ERROR", str(exc))
    finally:
        _drop_cancel_event(run_id)


def _mark_failed(run_id: int, stage: str, code: str, message: str) -> None:
    factory_service.set_run_fields(
        run_id, status="FAILED", failed_stage=stage, error_code=code, error_message=message, completed_at=_utcnow(),
    )


def create_and_start_run(
    project_id: int, settings: Settings, service: VideoComposerService, force: bool = False
) -> FactoryRun:
    """Section 43: by default, a project whose latest run already
    COMPLETED is returned unchanged rather than silently rendering again
    -- `force=True` (an explicit "Render Again", not exercised by the
    one-click "Create & Produce" button) is what actually starts a fresh
    run in that case. A project with an already-*active* run always
    reuses it regardless of `force` (section 44 -- there is never a
    genuine reason to run the same project twice at once).
    """
    if not force:
        latest = factory_service.get_latest_run_for_project(project_id)
        if latest is not None and latest.status == "COMPLETED":
            return latest

    run, created = factory_service.create_run(project_id)
    if created:
        thread = threading.Thread(
            target=_execute_pipeline_sync, args=(run.id, project_id, settings, service), daemon=True
        )
        thread.start()
    return run


def _continue_run_sync(run_id: int, project_id: int, settings: Settings, service: VideoComposerService) -> None:
    cancel_event = _cancel_event_for(run_id)
    try:
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=draft.config,
        )
        _run_quality_and_proceed(run_id, project_id, plan, settings, cancel_event, service)
    except FactoryStageError as exc:
        _mark_failed(run_id, exc.stage, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001
        logger.exception("FactoryRun %s failed unexpectedly resuming from NEEDS_REVIEW", run_id)
        _mark_failed(run_id, "QUALITY_CHECK", "UNEXPECTED_ERROR", str(exc))
    finally:
        _drop_cancel_event(run_id)


def continue_run(run_id: int, settings: Settings, service: VideoComposerService) -> FactoryRun:
    """Section 17/18: resumes a paused run from QUALITY_CHECK only --
    Beat generation and asset assignment are never re-run. Whatever the
    user fixed (typically a manual asset assignment via the Beat editor)
    is picked up simply by re-reading the project's current BeatPlan.
    """
    run = factory_service.get_run(run_id)
    if run is None:
        raise NotFoundError("FactoryRun", run_id)
    if run.status != "NEEDS_REVIEW":
        raise ValidationError(f"{NOT_RESUMABLE}: only a NEEDS_REVIEW run can be continued (this run is {run.status}).")

    factory_service.set_run_fields(run_id, status="QUALITY_CHECK")
    thread = threading.Thread(
        target=_continue_run_sync, args=(run_id, run.project_id, settings, service), daemon=True
    )
    thread.start()
    return factory_service.get_run(run_id)


def retry_run(run_id: int, settings: Settings, service: VideoComposerService) -> FactoryRun:
    """Section 25: resumes from the stage that actually failed.
    RenderJob-stage failures (QUEUED/RENDERING) delegate to
    VideoComposerService's own existing retry_job() -- a fresh RenderJob,
    never a second render pipeline -- and skip Beat/asset/quality work
    entirely, since those already passed. Every earlier-stage failure
    simply re-invokes the full pipeline from the top; each stage's own
    reuse-detection (section 10) means already-completed work (existing
    beats, existing assignments) is free, so this naturally "resumes from
    the earliest invalid stage" without a second, parallel resume-logic
    implementation.
    """
    run = factory_service.get_run(run_id)
    if run is None:
        raise NotFoundError("FactoryRun", run_id)
    if run.status != "FAILED":
        raise ValidationError(f"{NOT_RESUMABLE}: only a FAILED run can be retried (this run is {run.status}).")

    if run.failed_stage in ("QUEUED", "RENDERING") and run.render_job_id is not None:
        new_job_id = service.retry_job(run.render_job_id)
        factory_service.set_run_fields(
            run_id, status="QUEUED", render_job_id=new_job_id,
            error_code=None, error_message=None, failed_stage=None, completed_at=None,
        )
        return factory_service.get_run(run_id)

    factory_service.set_run_fields(
        run_id, status="PREPARING", error_code=None, error_message=None, failed_stage=None, completed_at=None,
    )
    thread = threading.Thread(
        target=_execute_pipeline_sync, args=(run_id, run.project_id, settings, service), daemon=True
    )
    thread.start()
    return factory_service.get_run(run_id)


def cancel_run(run_id: int, service: VideoComposerService) -> FactoryRun:
    """Section 22/23: cancellation only ever stops the *run*, never the
    project (its BeatPlan/assignments are untouched and stay editable).
    A QUEUED/RENDERING run delegates straight to VideoComposerService's
    own existing cancel_job() -- the one real cancellation mechanism for
    an in-flight render (section 20's "do not implement another process
    termination mechanism").
    """
    run = factory_service.get_run(run_id)
    if run is None:
        raise NotFoundError("FactoryRun", run_id)
    if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
        return run

    if run.status in ("QUEUED", "RENDERING") and run.render_job_id is not None:
        service.cancel_job(run.render_job_id)
        factory_service.set_run_fields(run_id, status="CANCELLED", completed_at=_utcnow())
    else:
        _cancel_event_for(run_id).set()

    return factory_service.get_run(run_id)


# -- Batch coordinator (section 31-34) -------------------------------------


def run_batch_factory(batch_id: int, settings: Settings, service: VideoComposerService) -> int:
    """Not a BatchFactoryPipeline -- exactly FactoryPipeline.run_project()
    (well, create_and_start_run/_execute_pipeline_sync) called once per
    eligible item, the same way app/api/v1/endpoints/batch_render.py's own
    _run_batch_beat_generation already bounds concurrent Claude calls with
    a ThreadPoolExecutor(max_workers=settings.max_concurrent_ai_generation)
    -- reused here verbatim (section 32: never start more AI calls at once
    than that limit allows), just wrapping the *whole* per-project pipeline
    instead of only its beat-generation step (harmless: every other stage
    is local and fast). Returns how many runs were actually started.
    """
    batch = get_batch_row(batch_id)
    to_start: list[tuple[int, int]] = []  # (run_id, project_id)
    for item in batch.items:
        if item.project_id is None or item.status in ("RENDERING", "COMPLETED", "CANCELLED"):
            continue
        latest = factory_service.get_latest_run_for_project(item.project_id)
        if latest is not None and latest.status == "COMPLETED":
            continue
        run, created = factory_service.create_run(item.project_id)
        if created:
            to_start.append((run.id, item.project_id))

    if not to_start:
        return 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, settings.max_concurrent_ai_generation)) as executor:
        futures = [
            executor.submit(_execute_pipeline_sync, run_id, project_id, settings, service)
            for run_id, project_id in to_start
        ]
        concurrent.futures.wait(futures)
    return len(to_start)


def continue_batch_factory(batch_id: int, settings: Settings, service: VideoComposerService) -> int:
    """Section 34's "[Continue Batch]" -- only NEEDS_REVIEW (Continue) and
    FAILED (Retry) projects are touched; COMPLETED/still-RENDERING ones
    are never re-run. Same bounded-executor shape as run_batch_factory,
    for the same reason (a retry can re-enter GENERATING_BEATS).
    """
    batch = get_batch_row(batch_id)
    tasks: list[tuple[str, FactoryRun]] = []
    for item in batch.items:
        if item.project_id is None:
            continue
        run = factory_service.get_active_run_for_project(item.project_id) or factory_service.get_latest_run_for_project(
            item.project_id
        )
        if run is None:
            continue
        if run.status == "NEEDS_REVIEW":
            tasks.append(("continue", run))
        elif run.status == "FAILED":
            tasks.append(("retry", run))

    if not tasks:
        return 0

    def _run_task(kind: str, run: FactoryRun) -> None:
        if kind == "continue":
            factory_service.set_run_fields(run.id, status="QUALITY_CHECK")
            _continue_run_sync(run.id, run.project_id, settings, service)
        else:
            if run.failed_stage in ("QUEUED", "RENDERING") and run.render_job_id is not None:
                new_job_id = service.retry_job(run.render_job_id)
                factory_service.set_run_fields(
                    run.id, status="QUEUED", render_job_id=new_job_id,
                    error_code=None, error_message=None, failed_stage=None, completed_at=None,
                )
            else:
                factory_service.set_run_fields(
                    run.id, status="PREPARING", error_code=None, error_message=None,
                    failed_stage=None, completed_at=None,
                )
                _execute_pipeline_sync(run.id, run.project_id, settings, service)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, settings.max_concurrent_ai_generation)) as executor:
        futures = [executor.submit(_run_task, kind, run) for kind, run in tasks]
        concurrent.futures.wait(futures)
    return len(tasks)


# -- Recovery / reconciliation (section 46-48) ------------------------------


def reconcile_factory_runs_on_startup(settings: Settings) -> int:
    """Called once from app/main.py's lifespan, *after*
    VideoComposerService.start() has already run its own
    _recover_pending_jobs() -- so by the time this runs, every
    VideoComposeJob's status is already settled (a crashed RUNNING job is
    already FAILED/RENDER_INTERRUPTED). Returns how many FactoryRuns were
    reconciled.
    """
    reconciled = 0
    for run in factory_service.list_active_runs():
        if run.status in ("QUEUED", "RENDERING") and run.render_job_id is not None:
            db = SessionLocal()
            try:
                job = db.get(VideoComposeJob, run.render_job_id)
                # error_code (failed jobs only) lives in the
                # .render/job_<id>/report.json sidecar, not a VideoComposeJob
                # column -- job_to_out reads it, and needs `job` still bound
                # to a live Session for its other (lazy-loaded) fields, so
                # this must happen before db.close(), not after.
                out = job_to_out(job, Path(settings.library_dir)) if job is not None else None
            finally:
                db.close()
            if job is None:
                _mark_failed(run.id, run.status, "FACTORY_INTERRUPTED", "The linked render job could not be found.")
            elif job.status == "completed":
                factory_service.set_run_fields(run.id, status="COMPLETED", completed_at=job.completed_at or _utcnow())
            elif job.status == "failed":
                _mark_failed(run.id, "RENDERING", out.error_code or RENDER_FAILED, job.error_message or "Render failed.")
            elif job.status == "cancelled":
                factory_service.set_run_fields(run.id, status="CANCELLED", completed_at=job.completed_at or _utcnow())
            else:
                # Still queued/running somehow -- shouldn't happen given
                # video_composer's own recovery already ran, but never
                # leave a run claiming RUNNING forever regardless (section 46).
                _mark_failed(run.id, run.status, "FACTORY_INTERRUPTED", "Application restarted while this run was rendering.")
        else:
            _mark_failed(
                run.id, run.status, "FACTORY_INTERRUPTED",
                f"Application restarted while this run was in {run.status}.",
            )
        reconciled += 1
    return reconciled


# -- render.job.* event handlers (section 21/51 -- reuse the existing
# EventBus, never a second one) ---------------------------------------------


def _find_run_by_render_job(job_id: int) -> FactoryRun | None:
    db = SessionLocal()
    try:
        run = (
            db.query(FactoryRun)
            .filter(FactoryRun.render_job_id == job_id, FactoryRun.status.in_(("QUEUED", "RENDERING")))
            .order_by(FactoryRun.id.desc())
            .first()
        )
        if run is not None:
            db.expunge(run)
        return run
    finally:
        db.close()


def _on_render_job_started(payload: dict) -> None:
    run = _find_run_by_render_job(payload["job_id"])
    if run is not None and run.status == "QUEUED":
        factory_service.set_run_fields(run.id, status="RENDERING")


def _on_render_job_completed(payload: dict) -> None:
    run = _find_run_by_render_job(payload["job_id"])
    if run is not None:
        factory_service.set_run_fields(run.id, status="COMPLETED", completed_at=_utcnow())


def _on_render_job_failed(payload: dict) -> None:
    run = _find_run_by_render_job(payload["job_id"])
    if run is not None:
        _mark_failed(run.id, "RENDERING", payload.get("error_code") or RENDER_FAILED, "The render failed.")


def _on_render_job_cancelled(payload: dict) -> None:
    run = _find_run_by_render_job(payload["job_id"])
    if run is not None:
        factory_service.set_run_fields(run.id, status="CANCELLED", completed_at=_utcnow())


def register_factory_event_handlers(event_bus: EventBus) -> None:
    event_bus.subscribe("render.job.started", _on_render_job_started)
    event_bus.subscribe("render.job.completed", _on_render_job_completed)
    event_bus.subscribe("render.job.failed", _on_render_job_failed)
    event_bus.subscribe("render.job.cancelled", _on_render_job_cancelled)


# -- API ---------------------------------------------------------------


def _run_or_404(run_id: int) -> FactoryRun:
    run = factory_service.get_run(run_id)
    if run is None:
        raise NotFoundError("FactoryRun", run_id)
    return run


@router.post("/projects/{project_id}/factory-run", response_model=FactoryRunOut, status_code=201)
def start_factory_run(
    project_id: int,
    force: bool = False,
    settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
    db: Session = Depends(get_db),
) -> FactoryRun:
    if db.get(Project, project_id) is None:
        raise NotFoundError("Project", project_id)
    return create_and_start_run(project_id, settings, service, force=force)


@router.get("/projects/{project_id}/factory-run", response_model=FactoryRunOut | None)
def get_latest_factory_run(project_id: int) -> FactoryRun | None:
    return factory_service.get_latest_run_for_project(project_id)


@router.get("/factory-runs/{run_id}", response_model=FactoryRunOut)
def get_factory_run(run_id: int) -> FactoryRun:
    return _run_or_404(run_id)


@router.post("/factory-runs/{run_id}/cancel", response_model=FactoryRunOut)
def cancel_factory_run(run_id: int, service: VideoComposerService = Depends(get_video_composer_service)) -> FactoryRun:
    _run_or_404(run_id)
    return cancel_run(run_id, service)


@router.post("/factory-runs/{run_id}/retry", response_model=FactoryRunOut)
def retry_factory_run(
    run_id: int, settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> FactoryRun:
    return retry_run(run_id, settings, service)


@router.post("/factory-runs/{run_id}/continue", response_model=FactoryRunOut)
def continue_factory_run(
    run_id: int, settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> FactoryRun:
    return continue_run(run_id, settings, service)


@router.post("/batches/{batch_id}/factory-run", response_model=dict)
def start_batch_factory(
    batch_id: int, settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> dict:
    started = run_batch_factory(batch_id, settings, service)
    return {"batch_id": batch_id, "runs_started": started}


@router.post("/batches/{batch_id}/factory-continue", response_model=dict)
def continue_batch_factory_endpoint(
    batch_id: int, settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> dict:
    processed = continue_batch_factory(batch_id, settings, service)
    return {"batch_id": batch_id, "runs_processed": processed}
