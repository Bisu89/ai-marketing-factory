"""The Factory pipeline's per-stage worker functions, extracted from
factory_pipeline.py so more than one orchestrator can reuse them without
depending on factory_pipeline's own single-project orchestration, batch
engine, render.job.* event handlers, and HTTP routes.

Today the only consumer is factory_pipeline.py itself (it re-imports every
name below, so `from app.pipelines.factory_pipeline import
_stage_generate_voice` etc. keeps working unchanged). A future
story_pipeline.py (long-form AI story production -- see the plan doc) will
import from HERE instead of pulling in the whole 2000-line
factory_pipeline module.

Same composition-root rules as factory_pipeline.py: per app/modules/README.md
none of app.modules.factory/beat/asset/quality/batch/video_composer may
import each other, but this file (like factory_pipeline.py / batch_render.py)
is core HTTP-layer infrastructure, not a module, so it may import all of
them and stitch them together. No new render pipeline, queue, quality
engine, asset matcher, or Beat generator is implemented here -- every real
unit of work is still delegated to the same underlying services
factory_pipeline.py already delegated to. This file's own job is purely:
translate one stage's success/failure into a stable, user-facing error
code, and keep FactoryRun/FactoryCheckpoint bookkeeping consistent.

This module intentionally has NO APIRouter -- it is called, never routed.
"""

import logging
import threading
import time
from datetime import datetime, timezone

from pydantic import ValidationError as PydanticValidationError

from app.api.v1.endpoints.audio_generate import (
    audio_master_is_valid,
    audio_master_path,
    generate_project_audio_master,
)
from app.pipelines.batch_render import project_composition_plan
from app.api.v1.endpoints.beat_generate import generate_beat_plan
from app.api.v1.endpoints.caption_generate import captions_ass_path, captions_is_valid, generate_project_captions
from app.api.v1.endpoints.composition_render import render_composition
from app.api.v1.endpoints.content_generate import (
    ContentProviderTimeout,
    InvalidContentResponse,
    ScriptValidationError,
    generate_content_brief,
    generate_script,
    validate_script_text,
)
from app.api.v1.endpoints.final_qa import run_final_qa
from app.api.v1.endpoints.imagegen_generate import ImageGenerationResult, generate_project_images
from app.api.v1.endpoints.motion_generate import generate_project_motion
from app.api.v1.endpoints.outro_generate import resolve_outro_clip
from app.api.v1.endpoints.package_generate import PackageError, generate_project_package
from app.api.v1.endpoints.quality_gate import compute_asset_confidence, run_quality_check, tokenize_prose
from app.api.v1.endpoints.voice_generate import generate_project_narration
from app.core import render_errors
from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings
from app.core.exceptions import ExternalServiceError, FileOperationError, NotFoundError, ValidationError
from app.core.render_profile import get_render_profile
from app.db.session import SessionLocal
from app.modules.ai.image_client import ImageGenError
from app.modules.ai.llm_client import resolve_ai_credentials
from app.modules.asset.service import AssetService
from app.modules.audio.schemas import AudioError
from app.modules.beat.project_service import (
    get_project_draft,
    set_project_generated_content,
    set_project_render_job_id,
    update_project_beat_plan,
)
from app.modules.beat.schemas import Beat, BeatPlan
from app.modules.caption.schemas import CaptionError
from app.modules.factory import service as factory_service
from app.modules.factory.models import FACTORY_STAGES
from app.modules.factory.schemas import (
    ASSET_MATCH_FAILED,
    BEAT_GENERATION_FAILED,
    CONTENT_GENERATION_FAILED,
    CONTENT_PROVIDER_TIMEOUT,
    FINAL_QA_FAILED,
    IMAGE_GENERATION_FAILED,
    INVALID_CONTENT_RESPONSE,
    INVALID_EXISTING_BEAT_PLAN,
    MOTION_ASSET_INVALID,
    MOTION_GENERATION_FAILED,
    QUALITY_BLOCKED,
    RENDER_FAILED,
    TTS_GENERATION_FAILED,
)
from app.modules.metadata.schemas import MetadataError
from app.modules.outro.schemas import OutroError
from app.modules.postqa.schemas import QAReport
from app.modules.thumbnail.schemas import ThumbnailError
from app.modules.video_composer.service import VideoComposerService
from app.modules.voice.schemas import VoiceError

logger = logging.getLogger(__name__)


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


def _bail_if_cancelled(run_id: int, cancel_event: threading.Event) -> bool:
    if not cancel_event.is_set():
        return False
    factory_service.set_run_fields(run_id, status="CANCELLED", completed_at=_utcnow())
    return True


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
    credentials = resolve_ai_credentials(settings)
    try:
        brief = generate_content_brief(credentials, idea, content_config)
        script = generate_script(credentials, brief, content_config, settings.content_words_per_second)
    except ContentProviderTimeout as exc:
        raise FactoryStageError("PREPARING_CONTENT", CONTENT_PROVIDER_TIMEOUT, str(exc)) from exc
    except InvalidContentResponse as exc:
        raise FactoryStageError("PREPARING_CONTENT", INVALID_CONTENT_RESPONSE, str(exc)) from exc
    except ScriptValidationError as exc:
        # generate_script's own bounded repair-retry loop already tried to
        # fix a too-long/too-short script (see content_generate.py's own
        # docstring on this) -- this is only reached once those retries are
        # exhausted, so exc.code (SCRIPT_TOO_LONG/SCRIPT_TOO_SHORT/...)
        # still needs to surface distinctly, not collapse into the generic
        # CONTENT_GENERATION_FAILED branch below (ScriptValidationError is
        # itself a ValidationError subclass, so it must be caught first).
        raise FactoryStageError("PREPARING_CONTENT", exc.code, str(exc)) from exc
    except (ValidationError, ExternalServiceError) as exc:
        raise FactoryStageError("PREPARING_CONTENT", CONTENT_GENERATION_FAILED, str(exc)) from exc

    script_text = script.to_narration_text()
    try:
        # Redundant with generate_script's own internal check above (same
        # script, same inputs) -- kept as a cheap defense-in-depth
        # safety net, not because this is expected to ever actually fail.
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
            generated = generate_beat_plan(
                resolve_ai_credentials(settings), script,
                idea=draft.idea,
                character_description=draft.config.visual_generation.image_style_prompt or None,
                tone=draft.config.content.tone,
                style=draft.config.content.style,
                target_duration=draft.config.content.target_duration,
            )
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


# -- Stage: PREPARING_VISUALS, real "ai_generated" mode (Task 59 -- see
# docs/features/59-ai-image-generation.md) ----------------------------------


def _stage_generate_images(project_id: int, settings: Settings) -> ImageGenerationResult:
    """Thin adapter over imagegen_generate.generate_project_images -- that
    function already owns the full idempotent per-beat reuse-or-regenerate
    decision (only beats with asset_id is None are ever touched), the real
    OpenAI Images API call, per-beat soft-failure handling, and Asset
    registration. This stage's own job is purely translating an
    ImageGenError into a FactoryStageError with a stable code, matching
    every other stage's own exception-translation shape. Only ever called
    when plan.config.visual_generation.mode == "ai_generated" -- the
    default "library" mode keeps today's exact pass-through/SKIPPED
    behavior for this same PREPARING_VISUALS slot (see
    _execute_pipeline_sync).
    """
    try:
        return generate_project_images(project_id, settings)
    except ImageGenError as exc:
        raise FactoryStageError("PREPARING_VISUALS", IMAGE_GENERATION_FAILED, str(exc)) from exc


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
    force: bool = False,
) -> None:
    """`force=True` (real bug report: "Continue Production" re-runs this
    exact check from scratch every time, so a warning that's still true --
    e.g. one beat's duration genuinely differs from the project average --
    re-pauses the run at NEEDS_REVIEW forever, with no way to actually
    proceed short of editing the beat plan) -- lets a human who has
    already SEEN this run's warnings once accept them and continue to
    render anyway, matching this module's own long-standing "NEEDS_REVIEW
    is override-able ('Render Anyway'), BLOCKED is not" doc comment
    (evaluate_readiness's own docstring) -- that comment described the
    intended behavior; forcing it through `continue_run`'s own `force`
    flag is what actually implements it. A real BLOCKED result (a hard
    content/asset problem, not a style/pacing preference) is never
    bypassed by `force` -- only a NEEDS_REVIEW (warnings-only, by
    construction: BLOCKED already raised above) pause is.
    """
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

    needs_review = report.status == "NEEDS_REVIEW" or policy_review_count > 0

    if needs_review and not force:
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
        run_id, "QUALITY_CHECK",
        metadata={"outcome": "OVERRIDDEN" if needs_review else "READY", "score": report.score},
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

    # Real user report: videos cut off abruptly right when narration
    # ends. An optional short trailing segment -- explicitly opted into
    # (config.outro.enabled + real text), never AI-derived -- appended
    # after the main composed video (see app/modules/outro's own
    # docstring). None when not configured, which is every existing
    # project (outro.enabled defaults False) -- render_composition/
    # _run_final_composition below are both fully unaffected in that case.
    try:
        resolved_outro_clip_path = resolve_outro_clip(
            project_id, plan.config, get_render_profile(plan.config.render.profile), settings
        )
    except OutroError as exc:
        raise FactoryStageError("READY_TO_RENDER", render_errors.OUTRO_RENDER_FAILED, str(exc)) from exc

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
            outro_clip_path=resolved_outro_clip_path,
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


# -- Stage: FINAL_QA (Task 28 -- see docs/features/54-final-qa.md) ---------


def _stage_final_qa(project_id: int, settings: Settings) -> QAReport:
    """Thin adapter over final_qa.run_final_qa -- that function already
    owns the full read-only check (section 38), never raising for any
    expected outcome (a QA FAIL is a normal, valid QAReport, not an
    exception -- see its own docstring). This stage's own job is purely
    settling the FactoryRun afterward (see _settle_after_final_qa), the
    same "thin adapter" shape as every other stage in this file.
    """
    return run_final_qa(project_id, settings)


def _settle_after_final_qa(run_id: int, report: QAReport) -> None:
    """Section 76's own explicit state diagram: FINAL_QA -> FAIL routes to
    NEEDS_REVIEW (never FAILED -- a QA failure is a valid, completed check
    that found a real problem, not a crash), with failed_stage="FINAL_QA"
    naming the repair entry point and error_code carrying the first FAIL
    check's own code so the frontend/Retry-classification machinery (see
    factory/schemas.py's own ERROR_CLASSIFICATION) has something concrete
    to show. This mirrors _run_quality_and_proceed's identical NEEDS_REVIEW
    handling for the pre-render Quality Gate (section 13's own "an
    unresolved review is an outcome of a valid check, not a failed one").

    PASS/PASS_WITH_WARNINGS both settle the run to COMPLETED -- a warning
    never blocks Ready-to-Post, matching every other soft-failure decision
    already made across this Factory (BGM-missing, Motion-cache-miss,
    Thumbnail-fallback-frame).
    """
    if report.status == "FAIL":
        first_fail = report.failures[0] if report.failures else None
        reason_count = max(len(report.failures) + len(report.warnings), 1)
        factory_service.set_run_fields(
            run_id, status="NEEDS_REVIEW", qa_status=report.status, qa_score=report.score,
            requires_human_review=True, review_reason_count=reason_count, failed_stage="FINAL_QA",
            error_code=first_fail.code if first_fail else FINAL_QA_FAILED,
            error_message=first_fail.message if first_fail else "Final QA found a problem with this project's package.",
        )
        factory_service.complete_checkpoint(
            run_id, "FINAL_QA",
            metadata={"outcome": "NEEDS_REVIEW", "score": report.score, "review_reason_count": reason_count},
        )
        return

    factory_service.set_run_fields(
        run_id, status="COMPLETED", completed_at=_utcnow(), qa_status=report.status, qa_score=report.score,
    )
    factory_service.complete_checkpoint(run_id, "FINAL_QA", metadata={"outcome": report.status, "score": report.score})


def _run_final_qa_and_settle(run_id: int, project_id: int, settings: Settings) -> None:
    """Shared by the render-completion handler (_on_render_job_completed)
    and every resume/retry path (continue_run, retry_run, and the batch
    equivalents) so "run FINAL_QA, then settle the run" is never
    duplicated -- the FINAL_QA checkpoint must already be started (status
    set to "FINAL_QA") by the caller before this runs.
    """
    try:
        report = _stage_final_qa(project_id, settings)
    except Exception as exc:  # noqa: BLE001 -- never a raw stack trace to the user (section 24)
        logger.exception("FactoryRun %s failed unexpectedly during FINAL_QA", run_id)
        _mark_failed(run_id, "FINAL_QA", "UNEXPECTED_ERROR", str(exc))
        return
    _settle_after_final_qa(run_id, report)
