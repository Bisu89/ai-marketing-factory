"""Batch video creation orchestration (Task 13 -- see
docs/features/40-batch-video-creation.md): the composition root for
everything that needs to know about more than one module at once --
app.modules.batch (Batch/BatchItem bookkeeping), app.modules.beat
(Project/BeatPlan/Template), app.modules.asset (resolving a Beat's
asset_id -> a real file path), app.modules.motion (resolving a motion
preset -> numeric render parameters), and app.modules.video_composer (the
existing render queue). Per app/modules/README.md, none of those modules
may import each other or this file; this file may import all of them,
exactly like app/api/v1/endpoints/composition_render.py already does for
the single-project render path -- this file is that same pattern applied
to "many projects at once."

Batch creation itself needs real cross-table transactional atomicity
(Task 13 section 14: "if project creation fails halfway, do not silently
create an unknown partial batch") -- app.modules.beat.project_service and
app.modules.batch.service each open/commit/close their OWN SessionLocal()
per call (by design, so a background thread can use them independently),
which can't provide atomicity *across* both modules' tables if called in
sequence. create_batch (below) is the one place that opens a single
shared session and constructs Project + Batch + BatchItem ORM objects
directly, committing once -- everywhere else in this file re-uses each
module's own per-call service functions, exactly as intended.
"""

import concurrent.futures
import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.beat_generate import generate_beat_plan
from app.api.v1.endpoints.composition_render import _resolve_classic_render_captions, render_composition
from app.api.v1.endpoints.motion_generate import resolve_effective_preset
from app.api.v1.endpoints.quality_gate import run_quality_check
from app.core.concurrency import ai_generation_semaphore
from app.core.config import Settings, get_settings
from app.modules.ai.llm_client import AICredentials, resolve_ai_credentials
from app.core.exceptions import FileOperationError, NotFoundError, ValidationError
from app.core.render_profile import get_render_profile
from app.db.session import SessionLocal, get_db
from app.modules.asset.service import AssetService
from app.modules.batch.models import Batch, BatchItem
from app.modules.batch.schemas import (
    BatchOut,
    BatchPreview,
    BatchPreviewItem,
    CreateBatchRequest,
    find_duplicate_ideas,
    normalize_idea,
    parse_idea_rows,
    parse_scripts,
)
from app.modules.batch.service import (
    get_batch as get_batch_row,
    project_name_for_item,
    recompute_batch_status,
    set_batch_status,
    set_item_fields,
)
from app.modules.beat.models import Project
from app.modules.beat.project_service import (
    get_project_beat_plan,
    get_project_draft,
    set_project_render_job_id,
    unique_project_slug,
    update_project_beat_plan,
)
from app.modules.beat.schemas import BUILTIN_TEMPLATES, BeatPlan, Template, new_project_draft
from app.modules.beat.service import load_custom_templates
from app.modules.composition.schemas import (
    CaptionPreset as CompositionCaptionPreset,
    CompositionPlan,
    Easing,
    OutputFormat,
    PositionRange,
    RotationRange,
    Scene,
    ScaleRange,
    SceneAudio,
    SceneCaption,
    SceneMotion,
    SceneTransition,
    TransitionType,
)
from app.modules.motion.service import build_motion_plan
from app.modules.video_composer.models import VideoComposeJob
from app.modules.video_composer.service import VideoComposerService

logger = logging.getLogger(__name__)
router = APIRouter()

_DEFAULT_TRANSITION_DURATION = 0.4


def get_video_composer_service(request: Request) -> VideoComposerService:
    return request.app.state.video_composer_service


def _templates_json_path(settings: Settings) -> Path:
    return Path(settings.library_dir) / "_beat" / "templates.json"


def _get_template_or_404(template_id: str, settings: Settings) -> Template:
    templates = {t.id: t for t in [*BUILTIN_TEMPLATES, *load_custom_templates(_templates_json_path(settings))]}
    if template_id not in templates:
        raise NotFoundError("Template", template_id)
    return templates[template_id]


def _validate_scripts(scripts_text: str) -> list[str]:
    scripts = parse_scripts(scripts_text)
    if not scripts:
        raise ValidationError("No scripts found -- paste at least one non-empty script, or separate several with a '---' line.")
    return scripts


# -- Batch idea import (Task 21 -- see
# docs/features/47-content-brief-script-engine.md sections 18-22) ----------


def _validate_and_maybe_dedupe_ideas(ideas_text: str, dedupe: bool):
    rows = parse_idea_rows(ideas_text)
    if not rows:
        raise ValidationError(
            "No ideas found -- enter at least one idea (one per line), or a CSV with an 'idea' column."
        )
    duplicates = find_duplicate_ideas([row.idea for row in rows])
    if dedupe and duplicates:
        seen: set[str] = set()
        deduped = []
        for row in rows:
            key = normalize_idea(row.idea)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped, {}
    return rows, duplicates


# -- Beat -> Scene conversion (server-side batch rendering has no frontend
# driving it beat-by-beat, unlike the single-project flow -- see module
# docstring) ------------------------------------------------------------


def beat_to_scene(beat, config, output_format: OutputFormat) -> Scene:
    # Task 23 (see docs/features/49-local-motion-engine.md sections 8/29/58)
    # -- manual Beat.motion_preset > deterministic auto-rotation (only when
    # the project opted into MotionProjectConfig.auto_rotate) > the fixed
    # project default. Every unset beat silently reusing the exact same
    # default_preset (this function's own pre-Task-23 behavior) is the
    # "every beat = zoom in" outcome section 29 explicitly calls out.
    effective_preset = resolve_effective_preset(beat, config).value.lower()
    motion_plan = build_motion_plan(effective_preset, duration=beat.duration, intensity=config.motion.intensity)
    return Scene(
        id=beat.id,
        order=beat.order,
        beat_id=beat.id,
        duration=beat.duration,
        source_asset_id=beat.asset_id,
        motion=SceneMotion(
            preset_name=effective_preset,
            scale=ScaleRange(start=motion_plan.scale.start, end=motion_plan.scale.end),
            position=PositionRange(
                x_start=motion_plan.position.x_start, y_start=motion_plan.position.y_start,
                x_end=motion_plan.position.x_end, y_end=motion_plan.position.y_end,
            ),
            rotation=RotationRange(start=motion_plan.rotation.start, end=motion_plan.rotation.end),
            easing=Easing(motion_plan.easing.value),
        ),
        caption=SceneCaption(text=beat.narration, preset=CompositionCaptionPreset(config.captions.preset)),
        audio=SceneAudio(sfx=None, sfx_volume=1.0, narration_asset_id=beat.narration_asset_id),
        transition=SceneTransition(type=TransitionType.CROSSFADE, duration=_DEFAULT_TRANSITION_DURATION),
        output_format=output_format,
    )


def project_composition_plan(
    plan: BeatPlan, asset_service: AssetService
) -> tuple[CompositionPlan, dict[int, str], dict[int, str]]:
    """Builds a real, renderable CompositionPlan from a Project's BeatPlan
    -- the server-side equivalent of buildScene()/buildCompositionPlan() in
    frontend/src/pages/VideoFactoryPage.tsx, needed because batch rendering
    has no human stepping through the wizard once per project. Raises
    ValidationError/NotFoundError/FileOperationError (never returns a
    partially-valid plan) -- this doubles as this task's own render-
    eligibility check (see _check_eligibility below): building the plan
    successfully *is* the check.

    Public (not `_`-prefixed), same as beat_to_scene above: Task 18's
    app/api/v1/endpoints/factory_pipeline.py -- another composition root --
    reuses both directly for its own RENDER stage rather than duplicating
    this Beat-plan-to-CompositionPlan translation a second time.
    """
    if not plan.beats:
        raise ValidationError("No beats generated yet.")

    render_profile = get_render_profile(plan.config.render.profile)
    output_format = OutputFormat(width=render_profile.width, height=render_profile.height, fps=render_profile.fps)

    scenes: list[Scene] = []
    asset_paths: dict[int, str] = {}
    narration_asset_paths: dict[int, str] = {}
    for beat in plan.ordered_beats():
        if beat.asset_id is None:
            raise ValidationError(f"Beat {beat.order}: no visual asset assigned.")
        asset = asset_service.get(beat.asset_id)
        if not Path(asset.path).exists():
            raise FileOperationError(f"Beat {beat.order}: asset file is missing: {asset.path}")
        asset_paths[beat.asset_id] = asset.path

        if beat.narration_asset_id is not None:
            narration_asset = asset_service.get(beat.narration_asset_id)
            if not Path(narration_asset.path).exists():
                raise FileOperationError(f"Beat {beat.order}: narration asset file is missing: {narration_asset.path}")
            narration_asset_paths[beat.narration_asset_id] = narration_asset.path

        scenes.append(beat_to_scene(beat, plan.config, output_format))

    composition_plan = CompositionPlan(
        video_id=None,
        narration_script=" ".join(beat.narration or "" for beat in plan.ordered_beats()),
        voice="en-US-GuyNeural",
        language=None,
        narration_volume=1.0,
        music_path=None,
        music_volume=plan.config.audio.music_volume,
        music_ducking_ratio=8.0 if plan.config.audio.ducking else 1.0,
        fade_in_sec=0.0,
        fade_out_sec=0.0,
        caption_preset=CompositionCaptionPreset(plan.config.captions.preset),
        scenes=scenes,
    )
    return composition_plan, asset_paths, narration_asset_paths


def _check_eligibility(project_id: int, asset_service: AssetService) -> tuple[bool, str | None]:
    try:
        plan = get_project_beat_plan(project_id)
    except NotFoundError as exc:
        return False, str(exc)
    except PydanticValidationError:
        # A beat-less (or otherwise not-yet-valid) draft fails BeatPlan's
        # own min_length=1 validator -- a real, expected lifecycle state
        # (see ProjectOut's docstring), not a system error.
        return False, "No beats generated yet."
    try:
        project_composition_plan(plan, asset_service)
    except (ValidationError, NotFoundError, FileOperationError) as exc:
        return False, str(exc)
    return True, None


# -- Preview + create ---------------------------------------------------


@router.post("/batches/preview", response_model=BatchPreview)
def preview_batch(payload: CreateBatchRequest, settings: Settings = Depends(get_settings)) -> BatchPreview:
    _get_template_or_404(payload.template_id, settings)

    if payload.scripts_text and payload.scripts_text.strip():
        scripts = _validate_scripts(payload.scripts_text)
        items = [
            BatchPreviewItem(
                index=index,
                project_name=project_name_for_item(payload.name, index),
                script_preview=(script[:140] + "...") if len(script) > 140 else script,
            )
            for index, script in enumerate(scripts, start=1)
        ]
        return BatchPreview(template_id=payload.template_id, script_count=len(scripts), items=items)

    if payload.ideas_text and payload.ideas_text.strip():
        rows, duplicates = _validate_and_maybe_dedupe_ideas(payload.ideas_text, payload.dedupe)
        duplicate_positions = {pos for indexes in duplicates.values() for pos in indexes}
        items = []
        for pos, row in enumerate(rows):
            index = pos + 1
            preview_text = f"Idea: {row.idea}"
            items.append(BatchPreviewItem(
                index=index, project_name=project_name_for_item(payload.name, index),
                script_preview=(preview_text[:140] + "...") if len(preview_text) > 140 else preview_text,
                is_duplicate=pos in duplicate_positions,
            ))
        return BatchPreview(
            template_id=payload.template_id, script_count=len(rows), items=items,
            duplicate_count=len(duplicate_positions),
        )

    raise ValidationError("Either scripts_text or ideas_text must be provided.")


@router.post("/batches", response_model=BatchOut, status_code=201)
def create_batch(payload: CreateBatchRequest, settings: Settings = Depends(get_settings)) -> BatchOut:
    template = _get_template_or_404(payload.template_id, settings)

    if payload.scripts_text and payload.scripts_text.strip():
        scripts = _validate_scripts(payload.scripts_text)
        db = SessionLocal()
        try:
            batch = Batch(name=payload.name, template_id=template.id, status="DRAFT")
            db.add(batch)
            db.flush()  # assigns batch.id without committing yet

            for index, script in enumerate(scripts, start=1):
                project_name = project_name_for_item(payload.name, index)
                config_snapshot = template.config.model_copy(deep=True)
                project = Project(
                    name=project_name,
                    slug=unique_project_slug(project_name, db),
                    beat_plan_json=new_project_draft(script, project_name, config_snapshot),
                )
                db.add(project)
                db.flush()  # assigns project.id
                db.add(BatchItem(
                    batch_id=batch.id, index=index, script_text=script, project_id=project.id, status="PROJECT_CREATED"
                ))

            db.commit()
            batch_id = batch.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return BatchOut.model_validate(get_batch_row(batch_id), from_attributes=True)

    if payload.ideas_text and payload.ideas_text.strip():
        rows, _duplicates = _validate_and_maybe_dedupe_ideas(payload.ideas_text, payload.dedupe)
        templates_by_id = {t.id: t for t in [*BUILTIN_TEMPLATES, *load_custom_templates(_templates_json_path(settings))]}

        db = SessionLocal()
        try:
            batch = Batch(name=payload.name, template_id=template.id, status="DRAFT")
            db.add(batch)
            db.flush()

            for pos, row in enumerate(rows):
                index = pos + 1
                project_name = project_name_for_item(payload.name, index)
                # Section 22's per-item overrides -- only ever set from a
                # CSV row (plain one-idea-per-line rows have none, see
                # parse_idea_rows); an unknown template id falls back to the
                # batch's own default rather than failing the whole batch
                # over one bad row (section 20: not a strict spreadsheet
                # importer).
                row_template = templates_by_id.get(row.template_id, template) if row.template_id else template
                config_snapshot = row_template.config.model_copy(deep=True)
                if row.language:
                    config_snapshot.content.language = row.language
                if row.target_duration:
                    config_snapshot.content.target_duration = row.target_duration

                project = Project(
                    name=project_name,
                    slug=unique_project_slug(project_name, db),
                    beat_plan_json=new_project_draft(None, project_name, config_snapshot, idea=row.idea, script_locked=False),
                )
                db.add(project)
                db.flush()
                # BatchItem.script_text is NOT NULLABLE (the old script-based
                # flow's own per-item raw-text column) -- for an idea-based
                # item this holds the idea text itself, the closest
                # equivalent of "what the user originally typed for this
                # item." This batch's own content/beat generation runs
                # through FactoryPipeline (see factory_pipeline.py's
                # run_batch_factory), never batch_render.py's own
                # _generate_beats_for_item/render_batch below, which only
                # ever look at BatchItem.status, not this column's content.
                db.add(BatchItem(
                    batch_id=batch.id, index=index, script_text=row.idea, project_id=project.id, status="PROJECT_CREATED"
                ))

            db.commit()
            batch_id = batch.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return BatchOut.model_validate(get_batch_row(batch_id), from_attributes=True)

    raise ValidationError("Either scripts_text or ideas_text must be provided.")


# -- Beat generation (bounded concurrency, background thread) -----------


def _generate_beats_for_item(item_id: int, project_id: int, script_text: str, credentials: AICredentials | None) -> None:
    try:
        # Task 20: shares app.core.concurrency's process-wide AI semaphore
        # with app/api/v1/endpoints/factory_pipeline.py's own Beat stage --
        # this ThreadPoolExecutor's own max_workers=max_concurrent_ai_generation
        # (see _run_batch_beat_generation) already bounds *this flow's own*
        # concurrent calls; the shared semaphore additionally bounds the
        # combined total if this flow and the factory batch engine both
        # happen to be generating beats at the same time.
        with ai_generation_semaphore:
            generated = generate_beat_plan(credentials, script_text)
    except Exception as exc:
        logger.exception("Batch item %s beat generation failed", item_id)
        set_item_fields(item_id, status="FAILED", error_message=str(exc))
        return

    try:
        draft = get_project_draft(project_id)
        full_plan = BeatPlan(
            script_text=generated.script_text, beats=generated.beats,
            project_name=draft.project_name, config=draft.config,
            # Task 21 -- carried through so an idea-based item accidentally
            # run through this older, script-only flow doesn't lose its
            # idea/content_brief/lock (see factory_pipeline.py's own
            # _stage_generate_beats for the identical fix and reasoning).
            idea=draft.idea, content_brief=draft.content_brief, script_locked=draft.script_locked,
        )
        update_project_beat_plan(project_id, full_plan)
        set_item_fields(item_id, status="BEATS_READY", error_message=None)
    except Exception as exc:
        logger.exception("Batch item %s failed to persist generated beats", item_id)
        set_item_fields(item_id, status="FAILED", error_message=str(exc))


def _run_batch_beat_generation(batch_id: int, credentials: AICredentials | None, max_workers: int) -> None:
    batch = get_batch_row(batch_id)
    pending = [item for item in batch.items if item.status == "PROJECT_CREATED"]
    if not pending:
        recompute_batch_status(batch_id)
        return
    # Bounded concurrency (Task 13 section 16): never more than
    # max_concurrent_ai_generation AI provider calls in flight at once,
    # regardless of how many items are pending.
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = [
            executor.submit(_generate_beats_for_item, item.id, item.project_id, item.script_text, credentials)
            for item in pending
        ]
        concurrent.futures.wait(futures)
    recompute_batch_status(batch_id)


@router.post("/batches/{batch_id}/generate-beats", response_model=BatchOut)
def generate_beats_for_batch(batch_id: int, settings: Settings = Depends(get_settings)) -> BatchOut:
    batch = get_batch_row(batch_id)
    pending = [item for item in batch.items if item.status == "PROJECT_CREATED"]
    if pending:
        set_batch_status(batch_id, "PROCESSING")
        thread = threading.Thread(
            target=_run_batch_beat_generation,
            args=(batch_id, resolve_ai_credentials(settings), settings.max_concurrent_ai_generation),
            daemon=True,
        )
        thread.start()
    return BatchOut.model_validate(get_batch_row(batch_id), from_attributes=True)


# -- Render all (reuses the existing RenderJob/LocalRenderQueue, never a
# second queue/worker -- see module docstring) ---------------------------


@router.post("/batches/{batch_id}/render", response_model=BatchOut)
def render_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> BatchOut:
    batch = get_batch_row(batch_id)
    asset_service = AssetService(db)

    for item in batch.items:
        if item.status != "BEATS_READY":
            continue  # not eligible yet, already rendering/terminal -- untouched (Task 13 section 21)

        try:
            plan = get_project_beat_plan(item.project_id)
            composition_plan, asset_paths, narration_asset_paths = project_composition_plan(plan, asset_service)
        except (ValidationError, NotFoundError, FileOperationError) as exc:
            set_item_fields(item.id, status="SKIPPED", error_message=str(exc))
            continue

        # Task 16 (see docs/features/42-content-quality-gate.md): a plan
        # that builds successfully can still be a bad idea to render --
        # BLOCKED is never enqueued; NEEDS_REVIEW is skipped by this
        # batch's own default policy (section 30's own explicit "skip until
        # reviewed," not silently rendered). Neither status touches
        # render_job_id or the render queue at all.
        quality_report = run_quality_check(plan.beats, plan.config, asset_service)
        if quality_report.status == "BLOCKED":
            set_item_fields(
                item.id, status="SKIPPED",
                error_message="Quality Gate: " + "; ".join(issue.message for issue in quality_report.issues),
            )
            continue
        if quality_report.status == "NEEDS_REVIEW":
            set_item_fields(
                item.id, status="NEEDS_REVIEW",
                error_message="Quality Gate: " + "; ".join(issue.message for issue in quality_report.warnings),
            )
            continue

        # See docs/features/56-classic-render-captions.md -- same fix as
        # the classic Quick Render endpoint: without this, a local-voice
        # Batch Render never burns captions even when the item's own
        # project already has a valid captions.ass.
        resolved_captions_path = _resolve_classic_render_captions(
            item.project_id, plan.config.captions.enabled, settings
        )
        try:
            job_id = render_composition(
                composition_plan, asset_paths, service,
                title=plan.project_name or f"Batch item {item.index}",
                narration_asset_paths=narration_asset_paths or None,
                profile=plan.config.render.profile,
                min_free_disk_mb=settings.min_free_disk_mb,
                project_id=item.project_id,
                library_dir=settings.library_dir,
                captions_ass_path=resolved_captions_path,
            )
        except (ValidationError, FileOperationError) as exc:
            set_item_fields(item.id, status="SKIPPED", error_message=str(exc))
            continue

        set_project_render_job_id(item.project_id, job_id)
        set_item_fields(item.id, status="RENDERING", render_job_id=job_id, error_message=None)

    recompute_batch_status(batch_id)
    return BatchOut.model_validate(get_batch_row(batch_id), from_attributes=True)


# -- Sync render status from VideoComposeJob + eligibility-aware detail --


def _sync_batch_items(batch: Batch, db: Session) -> None:
    for item in batch.items:
        if item.status != "RENDERING" or item.render_job_id is None:
            continue
        job = db.get(VideoComposeJob, item.render_job_id)
        if job is None:
            continue
        if job.status == "completed":
            set_item_fields(item.id, status="COMPLETED", error_message=None)
        elif job.status == "failed":
            set_item_fields(item.id, status="FAILED", error_message=job.error_message)
        elif job.status == "cancelled":
            set_item_fields(item.id, status="CANCELLED", error_message=None)
        # else still queued/running -- leave as RENDERING, nothing to sync yet.


@router.post("/batches/{batch_id}/sync", response_model=BatchOut)
def sync_batch(batch_id: int, db: Session = Depends(get_db)) -> BatchOut:
    batch = get_batch_row(batch_id)
    _sync_batch_items(batch, db)
    recompute_batch_status(batch_id)
    return BatchOut.model_validate(get_batch_row(batch_id), from_attributes=True)


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch_detail(batch_id: int, db: Session = Depends(get_db)) -> BatchOut:
    batch = get_batch_row(batch_id)
    _sync_batch_items(batch, db)
    recompute_batch_status(batch_id)
    batch = get_batch_row(batch_id)

    asset_service = AssetService(db)
    out = BatchOut.model_validate(batch, from_attributes=True)
    for item_out in out.items:
        if item_out.status == "BEATS_READY" and item_out.project_id is not None:
            item_out.eligible, item_out.ineligible_reason = _check_eligibility(item_out.project_id, asset_service)
            item_out.quality_status, item_out.quality_score = _check_quality_summary(item_out.project_id, asset_service)
    return out


def _check_quality_summary(project_id: int, asset_service: AssetService) -> tuple[str | None, int | None]:
    """Best-effort quality snapshot for the item list (Task 16) -- eligible/
    ineligible_reason (above) already explains an outright-broken plan;
    this is skipped rather than double-reported if that lookup itself
    fails (e.g. the project has no beats yet).
    """
    try:
        plan = get_project_beat_plan(project_id)
        report = run_quality_check(plan.beats, plan.config, asset_service)
        return report.status, report.score
    except Exception:
        return None, None


class BatchItemQualityOut(BaseModel):
    item_id: int
    project_id: int | None
    status: str  # READY | NEEDS_REVIEW | BLOCKED | NOT_READY (no beats yet / plan couldn't be built)
    score: int | None
    issues: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)


class BatchQualitySummary(BaseModel):
    batch_id: int
    ready: int
    needs_review: int
    blocked: int
    items: list[BatchItemQualityOut]


@router.post("/batches/{batch_id}/quality-check", response_model=BatchQualitySummary)
def check_batch_quality(batch_id: int, db: Session = Depends(get_db)) -> BatchQualitySummary:
    """Section 31/32's "Batch Quality" preview -- a pure, read-only dry run
    (no status changes, no RenderJobs) over every item that could plausibly
    be rendered right now (BEATS_READY) or is already waiting on a human
    (NEEDS_REVIEW), so re-checking after a fix shows the updated verdict.
    """
    batch = get_batch_row(batch_id)
    asset_service = AssetService(db)
    counts = {"READY": 0, "NEEDS_REVIEW": 0, "BLOCKED": 0}
    items: list[BatchItemQualityOut] = []

    for item in batch.items:
        if item.project_id is None or item.status not in ("BEATS_READY", "NEEDS_REVIEW"):
            continue
        try:
            plan = get_project_beat_plan(item.project_id)
            report = run_quality_check(plan.beats, plan.config, asset_service)
        except (ValidationError, NotFoundError, FileOperationError, PydanticValidationError) as exc:
            items.append(
                BatchItemQualityOut(
                    item_id=item.id, project_id=item.project_id, status="NOT_READY", score=None,
                    issues=[{"code": "NOT_READY", "severity": "error", "message": str(exc), "beat_id": None}],
                )
            )
            counts["BLOCKED"] += 1
            continue

        counts[report.status] += 1
        items.append(
            BatchItemQualityOut(
                item_id=item.id, project_id=item.project_id, status=report.status, score=report.score,
                issues=[issue.model_dump() for issue in report.issues],
                warnings=[issue.model_dump() for issue in report.warnings],
            )
        )

    return BatchQualitySummary(
        batch_id=batch_id, ready=counts["READY"], needs_review=counts["NEEDS_REVIEW"], blocked=counts["BLOCKED"], items=items
    )


# -- Cancel + retry --------------------------------------------------------


@router.post("/batches/{batch_id}/cancel", response_model=BatchOut)
def cancel_batch(batch_id: int, service: VideoComposerService = Depends(get_video_composer_service)) -> BatchOut:
    batch = get_batch_row(batch_id)
    for item in batch.items:
        if item.status in ("PROJECT_CREATED", "BEATS_READY"):
            set_item_fields(item.id, status="CANCELLED")
        elif item.status == "RENDERING" and item.render_job_id is not None:
            service.cancel_job(item.render_job_id)
            set_item_fields(item.id, status="CANCELLED")
        # COMPLETED/FAILED/SKIPPED/already-CANCELLED items are left as-is --
        # a completed output is never deleted (Task 13 section 23).
    recompute_batch_status(batch_id)
    return BatchOut.model_validate(get_batch_row(batch_id), from_attributes=True)


@router.post("/batches/{batch_id}/retry", response_model=BatchOut)
def retry_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
) -> BatchOut:
    """Only FAILED/SKIPPED items are touched (Task 13 section 24) -- never
    a completed one. Resets each to whichever stage it needs re-attempting
    from (PROJECT_CREATED if it never got beats, BEATS_READY if it just
    needs a fresh render attempt -- e.g. after the user fixed a missing
    asset), then re-runs exactly the same generate-beats/render-all code
    paths, scoped naturally by their own "only touch eligible-status
    items" filters.
    """
    batch = get_batch_row(batch_id)
    for item in batch.items:
        if item.status not in ("FAILED", "SKIPPED"):
            continue
        if item.project_id is None:
            continue
        draft = get_project_draft(item.project_id)
        if not draft.beats:
            set_item_fields(item.id, status="PROJECT_CREATED", error_message=None, render_job_id=None)
        else:
            set_item_fields(item.id, status="BEATS_READY", error_message=None, render_job_id=None)

    recompute_batch_status(batch_id)

    pending_for_beats = [item for item in get_batch_row(batch_id).items if item.status == "PROJECT_CREATED"]
    if pending_for_beats:
        set_batch_status(batch_id, "PROCESSING")
        thread = threading.Thread(
            target=_run_batch_beat_generation,
            args=(batch_id, resolve_ai_credentials(settings), settings.max_concurrent_ai_generation),
            daemon=True,
        )
        thread.start()

    return render_batch(batch_id, db=db, settings=settings, service=service)
