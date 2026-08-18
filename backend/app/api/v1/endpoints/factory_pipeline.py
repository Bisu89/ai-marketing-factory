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
from app.api.v1.endpoints.content_generate import (
    ContentProviderTimeout,
    InvalidContentResponse,
    ScriptValidationError,
    generate_content_brief,
    generate_script,
    validate_script_text,
)
from app.api.v1.endpoints.audio_generate import audio_master_is_valid, audio_master_path, generate_project_audio_master
from app.api.v1.endpoints.caption_generate import captions_ass_path, captions_is_valid, generate_project_captions
from app.api.v1.endpoints.motion_generate import generate_project_motion
from app.api.v1.endpoints.package_generate import PackageError, generate_project_package
from app.api.v1.endpoints.quality_gate import compute_asset_confidence, run_quality_check, tokenize_prose
from app.api.v1.endpoints.voice_generate import generate_project_narration
from app.core import render_errors
from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, FileOperationError, NotFoundError, ValidationError
from app.core.events import EventBus
from app.db.session import SessionLocal, get_db
from app.modules.asset.service import AssetService
from app.modules.audio.schemas import AudioError
from app.modules.batch import service as batch_service
from app.modules.caption.schemas import CaptionError
from app.modules.batch.models import Batch
from app.modules.batch.schemas import BatchOut
from app.modules.batch.service import get_batch as get_batch_row
from app.modules.beat.models import Project
from app.modules.beat.project_service import (
    get_project_draft,
    set_project_generated_content,
    set_project_render_job_id,
    update_project_beat_plan,
)
from app.modules.beat.schemas import Beat, BeatPlan
from app.modules.metadata.schemas import MetadataError
from app.modules.thumbnail.schemas import ThumbnailError
from app.modules.factory import service as factory_service
from app.modules.factory.models import FACTORY_STAGES, FactoryRun
from app.modules.factory.schemas import (
    ASSET_MATCH_FAILED,
    BEAT_GENERATION_FAILED,
    CONTENT_GENERATION_FAILED,
    CONTENT_PROVIDER_TIMEOUT,
    FactoryCheckpointOut,
    FactoryRunOut,
    INVALID_CONTENT_RESPONSE,
    INVALID_EXISTING_BEAT_PLAN,
    MOTION_ASSET_INVALID,
    MOTION_GENERATION_FAILED,
    NOT_RESUMABLE,
    QUALITY_BLOCKED,
    RENDER_FAILED,
    TTS_GENERATION_FAILED,
)
from app.modules.video_composer.models import VideoComposeJob
from app.modules.video_composer.schemas import job_to_out
from app.modules.video_composer.service import VideoComposerService
from app.modules.voice.schemas import VoiceError

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


# -- Stage: PREPARING_CONTENT (Task 21 -- see
# docs/features/47-content-brief-script-engine.md) -------------------------


def _stage_generate_content(project_id: int, settings: Settings) -> bool:
    """Section 24/27: idempotent, the same reuse-before-regenerate shape
    _stage_generate_beats already established for beats -- a project with a
    real script_text already (or script_locked, section 17: "human edits
    always win") skips this stage entirely; nothing is regenerated, nothing
    overwritten. Returns whether the AI was actually called (same "missing
    metrics key, not zero" convention _stage_generate_beats uses).

    A project with neither a script nor an idea is deliberately left alone
    here (not an error) -- GENERATING_BEATS' own existing, unmodified "no
    script to generate beats from" check is still what surfaces that as a
    real, user-facing BEAT_GENERATION_FAILED, exactly as it already did
    before this stage existed.
    """
    draft = get_project_draft(project_id)

    if draft.script_locked or (draft.script_text and draft.script_text.strip()):
        return False

    idea = (draft.idea or "").strip()
    if not idea:
        return False

    content_config = draft.config.content
    try:
        brief = generate_content_brief(settings.anthropic_api_key, idea, content_config)
        script = generate_script(settings.anthropic_api_key, brief, content_config)
    except ContentProviderTimeout as exc:
        raise FactoryStageError("PREPARING_CONTENT", CONTENT_PROVIDER_TIMEOUT, str(exc)) from exc
    except InvalidContentResponse as exc:
        raise FactoryStageError("PREPARING_CONTENT", INVALID_CONTENT_RESPONSE, str(exc)) from exc
    except (ValidationError, ExternalServiceError) as exc:
        raise FactoryStageError("PREPARING_CONTENT", CONTENT_GENERATION_FAILED, str(exc)) from exc

    script_text = script.to_narration_text()
    try:
        validate_script_text(script_text, content_config.target_duration, settings.content_words_per_second)
    except ScriptValidationError as exc:
        raise FactoryStageError("PREPARING_CONTENT", exc.code, str(exc)) from exc

    # Section 27: persist only after both the brief and the flattened
    # script have already passed real validation above -- never checkpoint
    # COMPLETED before this write, and never write before validating
    # (Task 19's own "validate, then persist, then checkpoint" ordering).
    set_project_generated_content(project_id, brief, script_text)
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
                idea=draft.idea, content_brief=draft.content_brief, script_locked=draft.script_locked,
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
        # Task 20 section 12: bounded to settings.max_concurrent_ai_generation
        # process-wide (app.core.concurrency), independently of
        # max_parallel_projects -- a batch running several projects at once
        # must never put more concurrent Claude calls in flight than this,
        # even if project-level concurrency is higher.
        with ai_generation_semaphore:
            generated = generate_beat_plan(settings.anthropic_api_key, script)
    except (ValidationError, ExternalServiceError) as exc:
        raise FactoryStageError("GENERATING_BEATS", BEAT_GENERATION_FAILED, str(exc)) from exc

    plan = BeatPlan(
        script_text=generated.script_text, beats=generated.beats,
        project_name=draft.project_name, config=draft.config,
        idea=draft.idea, content_brief=draft.content_brief, script_locked=draft.script_locked,
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


# -- Stage: GENERATING_MOTION (Task 23 -- see
# docs/features/49-local-motion-engine.md) ----------------------------------


def _stage_generate_motion(project_id: int, settings: Settings) -> bool:
    """Thin adapter over motion_generate.generate_project_motion -- that
    function already owns the full idempotent per-beat reuse-or-regenerate
    decision (fingerprint over asset + preset + intensity + output format,
    section 46), the real FFmpeg render, and ffprobe-based output
    validation. This stage's own job is purely translating
    app.core.exceptions into a FactoryStageError with a stable code
    (app.modules.motion.renderer raises the same ValidationError/
    FileOperationError vocabulary composition_render.py's own preflight
    already uses, not a module-specific error class -- see
    factory/schemas.py's own MOTION_ASSET_INVALID/MOTION_GENERATION_FAILED
    docstring for why these two, and only these two, codes cover it).
    """
    try:
        return generate_project_motion(project_id, settings)
    except ValidationError as exc:
        raise FactoryStageError("GENERATING_MOTION", MOTION_ASSET_INVALID, str(exc)) from exc
    except FileOperationError as exc:
        raise FactoryStageError("GENERATING_MOTION", MOTION_GENERATION_FAILED, str(exc)) from exc


# -- Stage: GENERATING_VOICE (Task 22 -- see
# docs/features/48-voice-factory-local-tts.md) ------------------------------


def _stage_generate_voice(project_id: int, settings: Settings) -> bool:
    """Thin adapter over voice_generate.generate_project_narration -- that
    function already owns the full idempotent reuse-or-regenerate decision
    (fingerprint over script text + voice settings, section 17/42's own
    established shape), the real TTS call, timing, per-beat cutting, and
    Asset registration. This stage's own job is purely translating a
    VoiceError into a FactoryStageError with a stable code (section 38),
    matching every other stage's own exception-translation shape.
    """
    try:
        return generate_project_narration(project_id, settings)
    except VoiceError as exc:
        raise FactoryStageError("GENERATING_VOICE", exc.code, str(exc)) from exc
    except (ValidationError, FileOperationError) as exc:
        raise FactoryStageError("GENERATING_VOICE", TTS_GENERATION_FAILED, str(exc)) from exc


# -- Stage: GENERATING_AUDIO (Task 24 -- see
# docs/features/50-audio-master.md) ------------------------------------


def _stage_generate_audio(project_id: int, settings: Settings) -> bool:
    """Thin adapter over audio_generate.generate_project_audio_master --
    that function already owns the full idempotent reuse-or-regenerate
    decision (fingerprint over narration + BGM selection + mix config,
    section 26/27), BGM selection, the real ffmpeg mix, and output
    validation. This stage's own job is purely translating an AudioError
    into a FactoryStageError with a stable code (section 52), matching
    every other stage's own exception-translation shape.
    """
    try:
        return generate_project_audio_master(project_id, settings)
    except AudioError as exc:
        raise FactoryStageError("GENERATING_AUDIO", exc.code, str(exc)) from exc


# -- Stage: GENERATING_CAPTIONS (Task 25 -- see
# docs/features/51-caption-engine.md) ------------------------------------


def _stage_generate_captions(project_id: int, settings: Settings) -> bool:
    """Thin adapter over caption_generate.generate_project_captions -- that
    function already owns the full idempotent reuse-or-regenerate decision
    (fingerprint over Beat narration + Voice-settled timing + caption
    config, section 37), segmentation, ASS serialization, and output
    validation. This stage's own job is purely translating a CaptionError
    into a FactoryStageError with a stable code, matching every other
    stage's own exception-translation shape.
    """
    try:
        return generate_project_captions(project_id, settings)
    except CaptionError as exc:
        raise FactoryStageError("GENERATING_CAPTIONS", exc.code, str(exc)) from exc


# -- Stage: QUALITY_CHECK + render handoff ---------------------------------


def _run_quality_and_proceed(
    run_id: int, project_id: int, plan: BeatPlan, settings: Settings,
    cancel_event: threading.Event, service: VideoComposerService,
) -> None:
    db = SessionLocal()
    try:
        asset_service = AssetService(db)
        t0 = time.monotonic()
        report = run_quality_check(plan.beats, plan.config, asset_service, project_id=project_id, settings=settings)
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
        # Section 13: this run's Quality checkpoint is COMPLETED here (the
        # Gate itself produced a real, current report -- see section 13's
        # "report corresponds to current project state," true by
        # construction since it was just computed above from the live
        # BeatPlan), even though the *run* pauses at NEEDS_REVIEW -- an
        # unresolved review is an outcome of a valid check, not a failed
        # one (mirrors section 12's identical distinction for Visual).
        factory_service.complete_checkpoint(
            run_id, "QUALITY_CHECK",
            metadata={"outcome": "NEEDS_REVIEW", "score": report.score, "review_reason_count": reason_count},
        )
        return

    # Completed before the cancellation check below (not after) -- the
    # Quality checkpoint's own outcome is already final at this point
    # regardless of whether the run goes on to cancel before rendering.
    factory_service.complete_checkpoint(
        run_id, "QUALITY_CHECK", metadata={"outcome": "READY", "score": report.score},
    )

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

    Task 26 (see docs/features/52-final-composer.md) -- a Factory render is
    always the Final Composer: it resolves Audio Master (required, section
    59) + Captions (optional, only when actually enabled and valid) +
    Watermark (optional, only when actually enabled and its Asset exists)
    up front, and hands all three straight to render_composition, which
    puts the job on the exact same, single existing render queue/worker as
    every other job -- never a second queue.
    """
    factory_service.set_run_fields(run_id, status="READY_TO_RENDER")
    factory_service.start_checkpoint(run_id, "READY_TO_RENDER")

    # Section 59: the Final Composer always requires a real Audio Master --
    # a Factory render never falls back to the old per-job TTS/local-
    # narration mixing pathway.
    if not audio_master_is_valid(project_id, settings):
        raise FactoryStageError(
            "READY_TO_RENDER", render_errors.AUDIO_MASTER_MISSING,
            "This project has no valid Audio Master to compose the final video from.",
        )
    resolved_audio_master_path = str(audio_master_path(project_id, settings.library_dir))

    # Section 14/17: captions are only wired in when actually enabled AND a
    # real, valid captions.ass exists -- disabled or stale-and-unrecovered
    # captions simply compose without them, never a hard failure at this
    # stage (Quality Gate's own CAPTIONS_ARTIFACT_MISSING warning, Task 25,
    # is what surfaces a stale artifact to the user).
    resolved_captions_path = None
    if plan.config.captions.enabled and captions_is_valid(project_id, settings):
        resolved_captions_path = str(captions_ass_path(project_id, settings.library_dir))

    # Section 18/19: watermark comes only from the Asset Library, never a
    # raw path -- a manually-selected Asset that no longer exists is a
    # genuine, user-facing problem (same reasoning as audio_generate.py's
    # own resolve_bgm_asset raising BGM_NOT_FOUND for the identical case).
    resolved_watermark_path = None
    watermark_config = plan.config.watermark
    if watermark_config.enabled and watermark_config.asset_id is not None:
        db = SessionLocal()
        try:
            try:
                watermark_asset = AssetService(db).get(watermark_config.asset_id)
            except NotFoundError as exc:
                raise FactoryStageError(
                    "READY_TO_RENDER", render_errors.WATERMARK_ARTIFACT_MISSING,
                    f"Selected watermark asset {watermark_config.asset_id} no longer exists.",
                ) from exc
            resolved_watermark_path = watermark_asset.path
        finally:
            db.close()

    db = SessionLocal()
    try:
        asset_service = AssetService(db)
        try:
            composition_plan, asset_paths, narration_asset_paths = project_composition_plan(plan, asset_service)
        except (ValidationError, NotFoundError, FileOperationError) as exc:
            raise FactoryStageError("READY_TO_RENDER", ASSET_MATCH_FAILED, str(exc)) from exc
    finally:
        db.close()
    factory_service.complete_checkpoint(run_id, "READY_TO_RENDER")

    factory_service.start_checkpoint(run_id, "QUEUED")
    try:
        job_id = render_composition(
            composition_plan, asset_paths, service,
            title=plan.project_name or f"Project {project_id}",
            narration_asset_paths=narration_asset_paths or None,
            profile=plan.config.render.profile,
            min_free_disk_mb=settings.min_free_disk_mb,
            project_id=project_id,
            library_dir=settings.library_dir,
            audio_master_path=resolved_audio_master_path,
            captions_ass_path=resolved_captions_path,
            watermark_path=resolved_watermark_path,
            watermark_position=watermark_config.position,
            watermark_opacity=watermark_config.opacity,
            watermark_scale=watermark_config.scale,
            watermark_margin_x=watermark_config.margin_x,
            watermark_margin_y=watermark_config.margin_y,
        )
    except (ValidationError, FileOperationError) as exc:
        raise FactoryStageError("QUEUED", RENDER_FAILED, str(exc)) from exc

    set_project_render_job_id(project_id, job_id)
    factory_service.set_run_fields(run_id, status="QUEUED", render_job_id=job_id)
    # Section 15: QUEUED itself is COMPLETED the instant a real RenderJob
    # row exists -- "the job was successfully handed to the existing
    # LocalRenderQueue," not "the render finished" (that's RENDERING's own
    # checkpoint, settled by the render.job.* event handlers below, since
    # this function is done once the job is queued -- see its own docstring).
    factory_service.complete_checkpoint(run_id, "QUEUED", metadata={"render_job_id": job_id})


# -- Stage: PACKAGING (Task 27 -- see
# docs/features/53-thumbnail-metadata-package.md) --------------------------


def _stage_package(run_id: int, project_id: int, settings: Settings) -> None:
    """Thin adapter over package_generate.generate_project_package -- that
    function already owns the full idempotent reuse-or-regenerate decision
    (independent fingerprints for the thumbnail and metadata.json, section
    40/41), frame extraction/scoring, title/description/hashtag
    derivation, and output validation. This stage's own job is purely
    translating a ThumbnailError/MetadataError/PackageError into a
    FactoryStageError with a stable code, matching every other stage's own
    exception-translation shape.
    """
    try:
        generate_project_package(project_id, settings)
    except (ThumbnailError, MetadataError, PackageError) as exc:
        raise FactoryStageError("PACKAGING", exc.code, str(exc)) from exc


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
        factory_service.start_checkpoint(run_id, "PREPARING")
        factory_service.complete_checkpoint(run_id, "PREPARING")
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "PREPARING_CONTENT"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.start_checkpoint(run_id, current_stage)
        t0 = time.monotonic()
        content_generated = _stage_generate_content(project_id, settings)
        if content_generated:
            factory_service.merge_metrics(run_id, content_generation_seconds=round(time.monotonic() - t0, 3))
        # Section 27: reaching this line already proves either (a) a valid
        # script_text now exists and passed validate_script_text, or (b)
        # this stage correctly had nothing to do (already had a script/no
        # idea at all) -- never "the AI request returned HTTP 200."
        factory_service.complete_checkpoint(run_id, current_stage, metadata={"generated": content_generated})
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "GENERATING_BEATS"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.start_checkpoint(run_id, current_stage)
        t0 = time.monotonic()
        plan, generated = _stage_generate_beats(project_id, settings)
        if generated:
            factory_service.merge_metrics(run_id, beat_generation_seconds=round(time.monotonic() - t0, 3))
        # Section 11: reaching this line already proves BeatPlan exists,
        # passed Pydantic validation, and has >=1 beat (BeatPlan itself
        # enforces beats non-empty -- see beat/schemas.py) -- exactly the
        # three conditions a COMPLETED Beat checkpoint requires.
        factory_service.complete_checkpoint(
            run_id, current_stage, metadata={"generated": generated, "beat_count": len(plan.beats)},
        )
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
        # "leave unassigned, let Quality Gate flag it" on its own. Checkpoint
        # SKIPPED, not COMPLETED -- there is genuinely no work to validate.
        current_stage = "PREPARING_VISUALS"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.skip_checkpoint(run_id, current_stage)
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "ASSIGNING_ASSETS"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.start_checkpoint(run_id, current_stage)
        t0 = time.monotonic()
        db = SessionLocal()
        try:
            plan = _stage_assign_assets(plan, AssetService(db))
        finally:
            db.close()
        update_project_beat_plan(project_id, plan)
        factory_service.merge_metrics(run_id, visual_assignment_seconds=round(time.monotonic() - t0, 3))
        # Section 12: an unassigned beat is not this *stage's* failure --
        # assignment ran to completion and left it for the Quality
        # Gate/factory review policy to flag (see _stage_assign_assets' own
        # docstring) -- so "assignment ran" and "every beat got assigned"
        # are deliberately different questions; only the former gates this
        # checkpoint.
        assigned_count = sum(1 for b in plan.ordered_beats() if b.asset_id is not None)
        factory_service.complete_checkpoint(
            run_id, current_stage, metadata={"beat_count": len(plan.beats), "assigned_count": assigned_count},
        )
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "GENERATING_VOICE"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.start_checkpoint(run_id, current_stage)
        t0 = time.monotonic()
        voice_generated = _stage_generate_voice(project_id, settings)
        if voice_generated:
            factory_service.merge_metrics(run_id, voice_generation_seconds=round(time.monotonic() - t0, 3))
        # Reload the plan -- generate_project_narration persists its own
        # per-beat narration_asset_id/start/end/duration writes directly
        # (see voice_generate.py), so `plan` here must be refreshed the
        # same way _stage_assign_assets' own update_project_beat_plan
        # already required a fresh read downstream. Critically, this is
        # also *why* GENERATING_MOTION runs after this stage, not before
        # (see models.py's own FACTORY_STAGES docstring) -- Motion needs
        # this refreshed `beat.duration`, not the original pre-Voice guess.
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=draft.config,
            idea=draft.idea, content_brief=draft.content_brief, script_locked=draft.script_locked,
        )
        factory_service.complete_checkpoint(run_id, current_stage, metadata={"generated": voice_generated})
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "GENERATING_MOTION"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.start_checkpoint(run_id, current_stage)
        t0 = time.monotonic()
        motion_generated = _stage_generate_motion(project_id, settings)
        if motion_generated:
            factory_service.merge_metrics(run_id, motion_generation_seconds=round(time.monotonic() - t0, 3))
        factory_service.complete_checkpoint(run_id, current_stage, metadata={"generated": motion_generated})
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "GENERATING_AUDIO"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.start_checkpoint(run_id, current_stage)
        t0 = time.monotonic()
        audio_generated = _stage_generate_audio(project_id, settings)
        if audio_generated:
            factory_service.merge_metrics(run_id, audio_generation_seconds=round(time.monotonic() - t0, 3))
        factory_service.complete_checkpoint(run_id, current_stage, metadata={"generated": audio_generated})
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "GENERATING_CAPTIONS"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.start_checkpoint(run_id, current_stage)
        t0 = time.monotonic()
        captions_generated = _stage_generate_captions(project_id, settings)
        if captions_generated:
            factory_service.merge_metrics(run_id, caption_generation_seconds=round(time.monotonic() - t0, 3))
        factory_service.complete_checkpoint(run_id, current_stage, metadata={"generated": captions_generated})
        if _bail_if_cancelled(run_id, cancel_event):
            return

        current_stage = "QUALITY_CHECK"
        factory_service.set_run_fields(run_id, status=current_stage)
        factory_service.start_checkpoint(run_id, current_stage)
        _run_quality_and_proceed(run_id, project_id, plan, settings, cancel_event, service)
    except FactoryStageError as exc:
        _mark_failed(run_id, exc.stage, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001 -- never a raw stack trace to the user (section 24)
        logger.exception("FactoryRun %s failed unexpectedly at %s", run_id, current_stage)
        _mark_failed(run_id, current_stage, "UNEXPECTED_ERROR", str(exc))
    finally:
        _drop_cancel_event(run_id)


def _mark_failed(run_id: int, stage: str, code: str, message: str) -> None:
    """The single funnel for every failure path (FactoryStageError, an
    unexpected exception, and reconcile_factory_runs_on_startup's own
    interruption handling) -- always settles both FactoryRun (the
    "current"/summary state) and that stage's own FactoryCheckpoint (Task
    19's durable per-stage record) together, so the two can never disagree
    about whether a given stage actually failed.
    """
    factory_service.set_run_fields(
        run_id, status="FAILED", failed_stage=stage, error_code=code, error_message=message, completed_at=_utcnow(),
    )
    if stage in FACTORY_STAGES:
        factory_service.fail_checkpoint(run_id, stage, code, message)


def _is_completed_run_stale(run: FactoryRun) -> bool:
    """Task 19 sections 14/29-34: a COMPLETED run's own Quality/Render
    result becomes stale once the project it rendered is edited afterward
    (a Beat, an asset assignment, motion, audio, or captions -- all
    serialized together in one Project.beat_plan_json, see that model's own
    docstring, so one signal covers the whole dependency graph). No new
    column is needed: Project.updated_at already bumps on every
    update_project_beat_plan() call (including this *same* run's own
    in-flight ASSIGNING_ASSETS stage, which always finishes chronologically
    before that same run's own completed_at -- so a run's own work never
    self-invalidates, only a *later*, independent edit does).
    """
    if run.completed_at is None:
        return False
    db = SessionLocal()
    try:
        project = db.get(Project, run.project_id)
    finally:
        db.close()
    if project is None:
        return False
    return project.updated_at > run.completed_at


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

    Task 19: a COMPLETED run edited afterward (see _is_completed_run_stale)
    is treated the same as `force=True` -- the previous render can no
    longer be trusted, so "Create & Produce" on an edited, already-produced
    project starts a fresh run instead of silently handing back stale
    output.
    """
    if not force:
        latest = factory_service.get_latest_run_for_project(project_id)
        if latest is not None and latest.status == "COMPLETED" and not _is_completed_run_stale(latest):
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
            idea=draft.idea, content_brief=draft.content_brief, script_locked=draft.script_locked,
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
    factory_service.start_checkpoint(run_id, "QUALITY_CHECK")
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
    entirely, since those already passed. A PACKAGING failure (Task 27 --
    see docs/features/53-thumbnail-metadata-package.md section 52) re-runs
    only _stage_package, synchronously, right here -- never re-rendering
    the video (there is no render-level cache, see docs/features/
    52-final-composer.md's own "Problems" section, so replaying the full
    pipeline would genuinely re-render from scratch, which section 52's
    own explicit "do not rerender the video" forbids). Every earlier-stage
    failure simply re-invokes the full pipeline from the top; each stage's
    own reuse-detection (section 10) means already-completed work
    (existing beats, existing assignments) is free, so this naturally
    "resumes from the earliest invalid stage" without a second, parallel
    resume-logic implementation.
    """
    run = factory_service.get_run(run_id)
    if run is None:
        raise NotFoundError("FactoryRun", run_id)
    if run.status != "FAILED":
        raise ValidationError(f"{NOT_RESUMABLE}: only a FAILED run can be retried (this run is {run.status}).")

    # Section 26: informational only -- this app has no automatic retry
    # loop (see FACTORY_MAX_ATTEMPTS' own docstring), so a manual Retry is
    # always allowed regardless of how many attempts have already happened.
    factory_service.increment_attempt(run_id)

    if run.failed_stage in ("QUEUED", "RENDERING") and run.render_job_id is not None:
        new_job_id = service.retry_job(run.render_job_id)
        factory_service.set_run_fields(
            run_id, status="QUEUED", render_job_id=new_job_id,
            error_code=None, error_message=None, failed_stage=None, completed_at=None,
        )
        factory_service.start_checkpoint(run_id, run.failed_stage)
        return factory_service.get_run(run_id)

    if run.failed_stage == "PACKAGING":
        factory_service.set_run_fields(
            run_id, status="PACKAGING", error_code=None, error_message=None, failed_stage=None, completed_at=None,
        )
        factory_service.start_checkpoint(run_id, "PACKAGING")
        try:
            _stage_package(run_id, run.project_id, settings)
        except FactoryStageError as exc:
            _mark_failed(run_id, exc.stage, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001 -- never a raw stack trace to the user (section 24)
            logger.exception("FactoryRun %s failed unexpectedly during PACKAGING retry", run_id)
            _mark_failed(run_id, "PACKAGING", "UNEXPECTED_ERROR", str(exc))
        else:
            factory_service.complete_checkpoint(run_id, "PACKAGING")
            factory_service.set_run_fields(run_id, status="COMPLETED", completed_at=_utcnow())
        _sync_batch_after_run_settled(run_id, run.project_id)
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


# -- Batch Engine (Task 20 -- see docs/features/46-factory-batch-engine.md)
#
# Deliberately NOT a second pipeline/queue/scheduler framework: every real
# unit of work is still _execute_pipeline_sync/_continue_run_sync/
# service.retry_job (all pre-existing, Task 18/19). This section's own job
# is exactly two things Task 18's original run_batch_factory/
# continue_batch_factory didn't do: (1) bound how many FactoryRuns run
# their *local* stages at once via settings.max_parallel_projects, using a
# plain concurrent.futures.ThreadPoolExecutor (its own internal work queue
# is already a correct, non-busy-looping FIFO bounded scheduler -- no
# custom one is built here), and (2) keep BatchItem.status/error_message in
# sync with the FactoryRun actually doing the work, so Batch's own
# item-derived status (recompute_batch_status) is never stale.
#
# Render concurrency is untouched and unbounded by anything in this
# section -- app.modules.video_composer.VideoComposerService's single
# worker thread already caps it at 1 (settings.max_parallel_renders is
# reporting-only, see that field's own docstring); a project's own
# ThreadPoolExecutor slot here is freed the instant _stage_render hands off
# to that existing queue, not when the render itself finishes.
# --------------------------------------------------------------------------


_batch_pause_events: dict[int, threading.Event] = {}
_batch_pause_lock = threading.Lock()


def _pause_event_for(batch_id: int) -> threading.Event:
    with _batch_pause_lock:
        event = _batch_pause_events.get(batch_id)
        if event is None:
            event = threading.Event()
            _batch_pause_events[batch_id] = event
        return event


def _drop_pause_event(batch_id: int) -> None:
    with _batch_pause_lock:
        _batch_pause_events.pop(batch_id, None)


def _sync_batch_item_from_run(item_id: int, run: FactoryRun) -> None:
    """The single place that translates a FactoryRun's granular status into
    BatchItem's own coarser vocabulary (section 7's own "derive batch state
    from actual items"). QUEUED/RENDERING (the render hand-off is
    asynchronous -- see _stage_render's own docstring) fall into the same
    "RUNNING" bucket as every local stage; their eventual COMPLETED/FAILED/
    CANCELLED settlement is synced separately, from the render.job.* event
    handlers below, since nothing is blocking on this call site to observe it.
    """
    if run.status == "COMPLETED":
        batch_service.set_item_fields(item_id, status="COMPLETED", render_job_id=run.render_job_id, error_message=None)
    elif run.status == "FAILED":
        batch_service.set_item_fields(item_id, status="FAILED", error_message=run.error_message)
    elif run.status == "CANCELLED":
        batch_service.set_item_fields(item_id, status="CANCELLED", error_message=None)
    elif run.status == "NEEDS_REVIEW":
        batch_service.set_item_fields(item_id, status="NEEDS_REVIEW", error_message=None)
    elif run.status == "READY_TO_RENDER":
        # Section 36's render_after_quality_pass=False policy -- a genuine,
        # non-terminal "done preparing, waiting for a manual render" state.
        batch_service.set_item_fields(item_id, status="READY_TO_RENDER", error_message=None)
    else:
        batch_service.set_item_fields(item_id, status="RUNNING", render_job_id=run.render_job_id, error_message=None)


def _recompute_batch_status_unless_paused(batch_id: int) -> None:
    """Section 21: pausing stops new work, it does not touch the Batch's
    own status while items already in flight settle -- calling the generic
    recompute_batch_status while PAUSED would otherwise silently overwrite
    "PAUSED"/"PAUSED_AFTER_RESTART" back to PROCESSING/DRAFT/etc the moment
    any one already-running item finished.
    """
    batch = get_batch_row(batch_id)
    if batch.status in ("PAUSED", "PAUSED_AFTER_RESTART"):
        return
    batch_service.recompute_batch_status(batch_id)


def _run_batch_item(
    item_id: int, project_id: int, settings: Settings, service: VideoComposerService, pause_event: threading.Event
) -> bool:
    """One ThreadPoolExecutor worker's unit of work -- claims the item
    (section 27/28's atomic claim; a lost race or a paused batch is a
    silent no-op, never an error), runs the existing single-project
    pipeline synchronously, then syncs BatchItem from whatever it settled
    at. Returns whether this call actually claimed and ran something (used
    for run_batch_factory's own "started" count).

    Section 40/41's own failure isolation: wrapped in its own try/except so
    one project's unexpected exception can never take down the
    ThreadPoolExecutor or any sibling submission -- though
    _execute_pipeline_sync already catches everything itself (Task 18), this
    is the outer boundary for claim_item/create_run/the sync call itself.
    """
    if pause_event.is_set():
        return False
    if not batch_service.claim_item(item_id):
        return False
    try:
        run, _created = factory_service.create_run(project_id)
        _execute_pipeline_sync(run.id, project_id, settings, service)
        settled = factory_service.get_run(run.id)
        _sync_batch_item_from_run(item_id, settled)
    except Exception:
        logger.exception("Batch item %s raised outside the FactoryRun's own error handling", item_id)
        batch_service.set_item_fields(item_id, status="FAILED", error_message="Unexpected error -- see server logs.")
    return True


def run_batch_factory(batch_id: int, settings: Settings, service: VideoComposerService) -> int:
    """The engine's own synchronous core -- exactly FactoryPipeline's
    existing create_and_start_run/_execute_pipeline_sync, called once per
    claimable item (section 15's own PENDING/PROJECT_CREATED/BEATS_READY/
    READY_TO_RENDER -- never FAILED/NEEDS_REVIEW/terminal, see
    batch_service.BATCH_ITEM_ENGINE_CLAIMABLE_STATUSES), bounded by
    settings.max_parallel_projects via a plain ThreadPoolExecutor. Blocks
    the calling thread until every *local*-stage pass this call started has
    settled (a queued/rendering item's own eventual outcome still arrives
    later, asynchronously) -- callers that must not block an HTTP request
    use start_batch_run below instead. Returns how many items this call
    actually claimed and started (never > however many were eligible, and
    never double-counts an item another concurrent call already claimed).
    """
    pause_event = _pause_event_for(batch_id)
    batch = get_batch_row(batch_id)
    candidates = [(item.id, item.project_id) for item in batch.items if item.project_id is not None]
    if not candidates:
        return 0

    started = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, settings.max_parallel_projects)) as executor:
        futures = [
            executor.submit(_run_batch_item, item_id, project_id, settings, service, pause_event)
            for item_id, project_id in candidates
        ]
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                started += 1

    if pause_event.is_set():
        batch_service.set_batch_status(batch_id, "PAUSED")
    else:
        batch_service.recompute_batch_status(batch_id)
        if get_batch_row(batch_id).status in ("COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED"):
            _drop_pause_event(batch_id)
    return started


def start_batch_run(batch_id: int, settings: Settings, service: VideoComposerService) -> None:
    """Non-blocking entry point for the live endpoint (section 29's "do not
    busy-loop, do not block the request") -- run_batch_factory itself stays
    a plain, directly-testable synchronous function (mirrors
    create_and_start_run's own thin-background-thread-around-a-sync-core
    shape for a single project).
    """
    thread = threading.Thread(target=run_batch_factory, args=(batch_id, settings, service), daemon=True)
    thread.start()


def continue_batch_factory(batch_id: int, settings: Settings, service: VideoComposerService) -> int:
    """Section 46's "[Continue Ready]" -- only NEEDS_REVIEW items. Distinct
    from retry_batch_failed below (section 45's separate "[Retry Failed]")
    since a batch's own review queue and its failure queue are different
    user workflows with different fixes. Claim-guarded the same way as
    run_batch_factory (from_statuses=("NEEDS_REVIEW",)) so two overlapping
    calls can't double-dispatch the same item.
    """
    pause_event = _pause_event_for(batch_id)
    batch = get_batch_row(batch_id)
    needs_review = [item for item in batch.items if item.status == "NEEDS_REVIEW" and item.project_id is not None]
    if not needs_review:
        return 0

    def _continue_one(item_id: int, project_id: int) -> bool:
        if pause_event.is_set():
            return False
        if not batch_service.claim_item(item_id, from_statuses=("NEEDS_REVIEW",)):
            return False
        try:
            run = factory_service.get_active_run_for_project(project_id) or factory_service.get_latest_run_for_project(
                project_id
            )
            if run is None or run.status != "NEEDS_REVIEW":
                batch_service.set_item_fields(item_id, status="NEEDS_REVIEW")  # nothing to continue -- put it back
                return False
            factory_service.set_run_fields(run.id, status="QUALITY_CHECK")
            factory_service.start_checkpoint(run.id, "QUALITY_CHECK")
            _continue_run_sync(run.id, project_id, settings, service)
            _sync_batch_item_from_run(item_id, factory_service.get_run(run.id))
        except Exception:
            logger.exception("Batch item %s failed unexpectedly while continuing", item_id)
            batch_service.set_item_fields(item_id, status="FAILED", error_message="Unexpected error -- see server logs.")
        return True

    processed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, settings.max_parallel_projects)) as executor:
        futures = [executor.submit(_continue_one, item.id, item.project_id) for item in needs_review]
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                processed += 1

    if pause_event.is_set():
        batch_service.set_batch_status(batch_id, "PAUSED")
    else:
        batch_service.recompute_batch_status(batch_id)
    return processed


def start_batch_continue(batch_id: int, settings: Settings, service: VideoComposerService) -> None:
    thread = threading.Thread(target=continue_batch_factory, args=(batch_id, settings, service), daemon=True)
    thread.start()


def retry_batch_failed(batch_id: int, settings: Settings, service: VideoComposerService) -> int:
    """Section 45's "[Retry Failed]" -- only FAILED items; a render-stage
    failure delegates to VideoComposerService's own retry_job (a fresh
    RenderJob, matching retry_run's own single-project logic exactly, never
    a second render pipeline); every earlier-stage failure re-invokes the
    full pipeline (cheap thanks to each stage's own reuse-detection). Never
    touches COMPLETED or NEEDS_REVIEW items (see continue_batch_factory for
    the latter).
    """
    pause_event = _pause_event_for(batch_id)
    batch = get_batch_row(batch_id)
    failed = [item for item in batch.items if item.status == "FAILED" and item.project_id is not None]
    if not failed:
        return 0

    def _retry_one(item_id: int, project_id: int) -> bool:
        if pause_event.is_set():
            return False
        if not batch_service.claim_item(item_id, from_statuses=("FAILED",)):
            return False
        try:
            run = factory_service.get_active_run_for_project(project_id) or factory_service.get_latest_run_for_project(
                project_id
            )
            if run is None or run.status != "FAILED":
                batch_service.set_item_fields(item_id, status="FAILED")
                return False
            factory_service.increment_attempt(run.id)
            if run.failed_stage in ("QUEUED", "RENDERING") and run.render_job_id is not None:
                new_job_id = service.retry_job(run.render_job_id)
                factory_service.set_run_fields(
                    run.id, status="QUEUED", render_job_id=new_job_id,
                    error_code=None, error_message=None, failed_stage=None, completed_at=None,
                )
                factory_service.start_checkpoint(run.id, run.failed_stage)
                _sync_batch_item_from_run(item_id, factory_service.get_run(run.id))
            elif run.failed_stage == "PACKAGING":
                # Task 27 section 52 -- resume Packaging only, never
                # re-render the video (same reasoning as retry_run's own
                # identical branch).
                factory_service.set_run_fields(
                    run.id, status="PACKAGING", error_code=None, error_message=None,
                    failed_stage=None, completed_at=None,
                )
                factory_service.start_checkpoint(run.id, "PACKAGING")
                try:
                    _stage_package(run.id, project_id, settings)
                except FactoryStageError as exc:
                    _mark_failed(run.id, exc.stage, exc.code, exc.message)
                else:
                    factory_service.complete_checkpoint(run.id, "PACKAGING")
                    factory_service.set_run_fields(run.id, status="COMPLETED", completed_at=_utcnow())
                _sync_batch_item_from_run(item_id, factory_service.get_run(run.id))
            else:
                factory_service.set_run_fields(
                    run.id, status="PREPARING", error_code=None, error_message=None,
                    failed_stage=None, completed_at=None,
                )
                _execute_pipeline_sync(run.id, project_id, settings, service)
                _sync_batch_item_from_run(item_id, factory_service.get_run(run.id))
        except Exception:
            logger.exception("Batch item %s failed unexpectedly while retrying", item_id)
            batch_service.set_item_fields(item_id, status="FAILED", error_message="Unexpected error -- see server logs.")
        return True

    processed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, settings.max_parallel_projects)) as executor:
        futures = [executor.submit(_retry_one, item.id, item.project_id) for item in failed]
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                processed += 1

    if pause_event.is_set():
        batch_service.set_batch_status(batch_id, "PAUSED")
    else:
        batch_service.recompute_batch_status(batch_id)
    return processed


def start_batch_retry_failed(batch_id: int, settings: Settings, service: VideoComposerService) -> None:
    thread = threading.Thread(target=retry_batch_failed, args=(batch_id, settings, service), daemon=True)
    thread.start()


def pause_batch_engine(batch_id: int) -> None:
    """Section 21: stops new items from being *claimed* -- items already
    RUNNING (local stages in another worker thread, or already handed off
    to the existing RenderQueue) are left to finish naturally, matching
    "running projects should normally finish." Idempotent: pausing an
    already-paused/terminal batch is a no-op.
    """
    batch = get_batch_row(batch_id)
    if batch.status not in ("PROCESSING",):
        return
    _pause_event_for(batch_id).set()
    batch_service.set_batch_status(batch_id, "PAUSED")


def resume_batch_engine(batch_id: int, settings: Settings, service: VideoComposerService) -> None:
    """Section 22: only PENDING/PROJECT_CREATED/BEATS_READY/READY_TO_RENDER
    items are picked up (run_batch_factory's own claim-based eligibility);
    a RUNNING item was never touched by pause in the first place, and a
    COMPLETED/FAILED/CANCELLED one is never silently restarted here.
    """
    batch = get_batch_row(batch_id)
    if batch.status not in ("PAUSED", "PAUSED_AFTER_RESTART"):
        raise ValidationError(f"Only a PAUSED batch can be resumed (this batch is {batch.status}).")
    _pause_event_for(batch_id).clear()
    batch_service.set_batch_status(batch_id, "PROCESSING")
    start_batch_run(batch_id, settings, service)


def cancel_batch_engine(batch_id: int, service: VideoComposerService) -> None:
    """Section 23/24: every still-claimable (not-yet-started) item becomes
    CANCELLED immediately and atomically (batch_service.bulk_cancel_claimable_items
    -- this alone also closes the race against a concurrently-running
    claim, see that function's own docstring); every currently-RUNNING item
    gets a real cancellation *request* through the existing single-project
    cancel_run (itself delegating to VideoComposerService.cancel_job for an
    in-flight render, or a cooperative cancel_event for a local stage) --
    never force-killed, never silently ignored. Already-COMPLETED/FAILED/
    NEEDS_REVIEW/SKIPPED items are left exactly as they are (section 24:
    "already completed projects remain COMPLETED").
    """
    _pause_event_for(batch_id).set()  # also stop any in-flight run_batch_factory from claiming anything further
    batch_service.bulk_cancel_claimable_items(batch_id)

    batch = get_batch_row(batch_id)
    for item in batch.items:
        if item.status != "RUNNING" or item.project_id is None:
            continue
        run = factory_service.get_active_run_for_project(item.project_id)
        if run is not None:
            cancel_run(run.id, service)
            _sync_batch_item_from_run(item.id, factory_service.get_run(run.id))

    batch_service.recompute_batch_status(batch_id)
    _drop_pause_event(batch_id)


def skip_batch_item(item_id: int) -> bool:
    """Section 51: a PENDING (or otherwise not-yet-started) item the user
    doesn't want processed -> SKIPPED, never rendered. Not a failure --
    excluded from any "N failed" count, and from run_batch_factory's own
    eligibility going forward (SKIPPED is a terminal status). Returns
    whether the skip actually took effect (False if the item had already
    moved past claimable, e.g. it started running a moment earlier).
    """
    return batch_service.claim_item(item_id, new_status="SKIPPED")


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
                # Section 15/16: job.status == "completed" already implies a
                # real, ffprobe-validated final.mp4 (VideoComposerService's
                # own _validate_final_output/atomic rename -- see
                # docs/features/37-e2e-pipeline-hardening.md) -- a job can
                # never reach "completed" with an invalid/partial output, so
                # there is nothing further to (re-)validate here.
                factory_service.set_run_fields(run.id, status="COMPLETED", completed_at=job.completed_at or _utcnow())
                factory_service.force_checkpoint_status(run.id, "QUEUED", "COMPLETED")
                factory_service.force_checkpoint_status(run.id, "RENDERING", "COMPLETED")
            elif job.status == "failed":
                _mark_failed(run.id, "RENDERING", out.error_code or RENDER_FAILED, job.error_message or "Render failed.")
                factory_service.force_checkpoint_status(run.id, "QUEUED", "COMPLETED")
            elif job.status == "cancelled":
                factory_service.set_run_fields(run.id, status="CANCELLED", completed_at=job.completed_at or _utcnow())
                factory_service.force_checkpoint_status(run.id, "QUEUED", "COMPLETED")
                factory_service.force_checkpoint_status(run.id, "RENDERING", "SKIPPED")
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


def reconcile_batches_on_startup() -> int:
    """Task 20 section 43/44: called once from app/main.py's lifespan,
    *after* reconcile_factory_runs_on_startup above has already settled
    every FactoryRun a batch's RUNNING items were waiting on -- so this
    function's own job is purely: (1) sync each such BatchItem from its
    now-settled FactoryRun (never regenerating/re-rendering anything
    itself), and (2) force every batch that was actively PROCESSING back to
    PAUSED_AFTER_RESTART, never silently resuming it. This is a desktop
    machine -- the user may be mid-task, a source drive may be unmounted, a
    credential may have changed (section 44) -- so an explicit
    "Resume Batch" is always required after a restart, no matter how close
    to finished the batch already was. Returns how many batches were paused.
    """
    paused = 0
    for batch in batch_service.list_batches():
        if batch.status != "PROCESSING":
            continue
        for item in batch.items:
            if item.status != "RUNNING" or item.project_id is None:
                continue
            run = factory_service.get_active_run_for_project(item.project_id) or factory_service.get_latest_run_for_project(
                item.project_id
            )
            if run is not None:
                _sync_batch_item_from_run(item.id, run)
        batch_service.set_batch_status(batch.id, "PAUSED_AFTER_RESTART")
        _drop_pause_event(batch.id)  # any pre-crash pause/cancel signal is meaningless in a new process
        paused += 1
    return paused


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
        factory_service.start_checkpoint(run.id, "RENDERING")


def _on_render_job_completed(payload: dict) -> None:
    # Section 15/16: this event only ever fires for a job that reached
    # VideoComposerService's own "completed" status, which already implies
    # a real, ffprobe-validated final.mp4 (atomic rename past
    # _validate_final_output -- see docs/features/37-e2e-pipeline-hardening.md)
    # -- there is no path where an invalid/partial output produces this
    # event, so PACKAGING never starts against unvalidated output.
    #
    # Task 27 (see docs/features/53-thumbnail-metadata-package.md section
    # 42): RENDERING no longer jumps straight to COMPLETED -- PACKAGING
    # (thumbnail.jpg + metadata.json) runs here first, synchronously, on
    # this same call stack (EventBus.publish's own "handlers run
    # synchronously" contract -- see app/core/events.py). This is still
    # VideoComposerService's own single worker thread underneath (the
    # publish() call that reaches this handler happens from inside that
    # worker's own _run_job/_run_final_composition), so running lightweight
    # local work here delays only the *next* queued render job's start by
    # a few seconds, never anything else -- exactly section 55's own "reuse
    # existing resource management, do not create a ThumbnailQueue."
    run = _find_run_by_render_job(payload["job_id"])
    if run is None:
        return
    factory_service.complete_checkpoint(run.id, "RENDERING")
    factory_service.set_run_fields(run.id, status="PACKAGING")
    factory_service.start_checkpoint(run.id, "PACKAGING")
    try:
        _stage_package(run.id, run.project_id, get_settings())
    except FactoryStageError as exc:
        _mark_failed(run.id, exc.stage, exc.code, exc.message)
        _sync_batch_after_run_settled(run.id, run.project_id)
        return
    except Exception as exc:  # noqa: BLE001 -- never a raw stack trace to the user (section 24)
        logger.exception("FactoryRun %s failed unexpectedly during PACKAGING", run.id)
        _mark_failed(run.id, "PACKAGING", "UNEXPECTED_ERROR", str(exc))
        _sync_batch_after_run_settled(run.id, run.project_id)
        return
    factory_service.complete_checkpoint(run.id, "PACKAGING")
    factory_service.set_run_fields(run.id, status="COMPLETED", completed_at=_utcnow())
    _sync_batch_after_run_settled(run.id, run.project_id)


def _on_render_job_failed(payload: dict) -> None:
    run = _find_run_by_render_job(payload["job_id"])
    if run is not None:
        _mark_failed(run.id, "RENDERING", payload.get("error_code") or RENDER_FAILED, "The render failed.")
        _sync_batch_after_run_settled(run.id, run.project_id)


def _on_render_job_cancelled(payload: dict) -> None:
    run = _find_run_by_render_job(payload["job_id"])
    if run is not None:
        factory_service.set_run_fields(run.id, status="CANCELLED", completed_at=_utcnow())
        factory_service.force_checkpoint_status(run.id, "RENDERING", "SKIPPED")
        _sync_batch_after_run_settled(run.id, run.project_id)


def _sync_batch_after_run_settled(run_id: int, project_id: int) -> None:
    """Task 20: the async tail of _run_batch_item -- a render's own
    eventual completion/failure/cancellation arrives here, well after the
    ThreadPoolExecutor worker that started it has already returned (see
    _stage_render's own docstring on why this hand-off is non-blocking).
    A no-op for a project that isn't part of any batch (item is None).
    """
    item = batch_service.get_batch_item_by_project(project_id)
    if item is None:
        return
    settled = factory_service.get_run(run_id)
    if settled is not None:
        _sync_batch_item_from_run(item.id, settled)
    _recompute_batch_status_unless_paused(item.batch_id)


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


@router.get("/factory-runs/{run_id}/checkpoints", response_model=list[FactoryCheckpointOut])
def get_factory_run_checkpoints(run_id: int) -> list:
    """Task 19 section 42's own "Production Run" detail view -- per-stage
    COMPLETED/FAILED/SKIPPED/RUNNING history, independent of FactoryRun's
    own single current `status` field.
    """
    _run_or_404(run_id)
    return factory_service.get_checkpoints(run_id)


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
    """Task 20: non-blocking (section 29) -- unlike Task 18's original
    synchronous version, this returns immediately once the background
    thread is started; the frontend already polls GET /batches/{id} for
    real progress afterward rather than trusting this response's own
    numbers (see frontend/src/pages/BatchDetailPage.tsx), so the response
    shape is kept exactly as before for zero frontend changes -- the
    number is simply always 0 now (nothing has been claimed yet by the
    time this returns), not a final count.
    """
    get_batch_row(batch_id)  # 404 if the batch itself doesn't exist
    batch_service.set_batch_status(batch_id, "PROCESSING")
    start_batch_run(batch_id, settings, service)
    return {"batch_id": batch_id, "runs_started": 0}


@router.post("/batches/{batch_id}/factory-continue", response_model=dict)
def continue_batch_factory_endpoint(
    batch_id: int, settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> dict:
    """Section 46's "[Continue Ready]" -- NEEDS_REVIEW items only (see
    continue_batch_factory's own docstring for why FAILED items are a
    separate action, POST /batches/{id}/factory-retry-failed below).
    """
    get_batch_row(batch_id)
    batch_service.set_batch_status(batch_id, "PROCESSING")
    start_batch_continue(batch_id, settings, service)
    return {"batch_id": batch_id, "runs_processed": 0}


@router.post("/batches/{batch_id}/factory-retry-failed", response_model=dict)
def retry_batch_failed_endpoint(
    batch_id: int, settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> dict:
    get_batch_row(batch_id)
    batch_service.set_batch_status(batch_id, "PROCESSING")
    start_batch_retry_failed(batch_id, settings, service)
    return {"batch_id": batch_id, "runs_processed": 0}


@router.post("/batches/{batch_id}/factory-pause", response_model=BatchOut)
def pause_batch_endpoint(batch_id: int) -> Batch:
    get_batch_row(batch_id)
    pause_batch_engine(batch_id)
    return get_batch_row(batch_id)


@router.post("/batches/{batch_id}/factory-resume", response_model=BatchOut)
def resume_batch_endpoint(
    batch_id: int, settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> Batch:
    get_batch_row(batch_id)
    resume_batch_engine(batch_id, settings, service)
    return get_batch_row(batch_id)


@router.post("/batches/{batch_id}/factory-cancel", response_model=BatchOut)
def cancel_batch_factory_endpoint(
    batch_id: int, service: VideoComposerService = Depends(get_video_composer_service)
) -> Batch:
    get_batch_row(batch_id)
    cancel_batch_engine(batch_id, service)
    return get_batch_row(batch_id)


@router.post("/batches/{batch_id}/items/{item_id}/skip", response_model=BatchOut)
def skip_batch_item_endpoint(batch_id: int, item_id: int) -> Batch:
    batch = get_batch_row(batch_id)
    if not any(item.id == item_id for item in batch.items):
        raise NotFoundError("BatchItem", item_id)
    skip_batch_item(item_id)
    batch_service.recompute_batch_status(batch_id)
    return get_batch_row(batch_id)
