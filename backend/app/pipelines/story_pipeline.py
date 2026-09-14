"""AI Storytelling Studio -- the story pipeline composition root (plan
Phase 3: Scene Director wiring + pre-flight cost/budget guard).

Per app/modules/README.md, `app.modules.story` never imports another
module, and `app.modules.scene_director` / `app.modules.ai` are pure
contracts that never import `beat`. This file is the one place allowed to
import all of them together -- exactly the split
app/api/v1/endpoints/quality_gate.py already uses (app.modules.quality +
app.modules.beat + app.modules.asset).

Phase 3 does NOT generate anything. It:

  GET  /stories/{id}/config          -- validate & normalise the stored
                                        project_config_json against
                                        app.modules.beat.schemas.ProjectConfig
                                        (the piece Phase 1 deliberately left
                                        opaque)
  POST /stories/{id}/classify-scenes -- run the deterministic Scene Director
                                        over every StoryScene, persist the
                                        4 sub-scores + composite + the
                                        STILL / STILL_WITH_MOTION / AI_VIDEO
                                        decision (never touching a scene a
                                        human froze with visual_mode_source
                                        = "USER")
  GET  /stories/{id}/cost-estimate    -- a conservative pre-flight
                                        CostEstimate for producing the story
                                        + a CostGuard verdict (OK / WARN /
                                        BLOCK / UNKNOWN)
  GET  /stories/{id}/scene-plan       -- read-only: every scene with its
                                        current scores/mode + the cost
                                        estimate, for a future Studio UI

The real resumable "advance this story" StoryRun pipeline (idea -> bible ->
chapters -> scenes -> compile) is Phase 4/5; this is the classifier +
estimator wired to real rows, nothing more.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, ValidationError as PydanticValidationError

from app.pipelines.story_stages import (
    StoryStageError,
    _stage_chapter_outline,
    _stage_character_bible,
    _stage_scene_breakdown,
    _stage_story_bible,
    _stage_story_development,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.ai.cost_estimator import CostEstimate, CostEstimateInput, LlmWorkItem, estimate_story
from app.modules.ai.image_client import IMAGE_COST_USD
from app.modules.beat.schemas import ProjectConfig
from app.modules.scene_director.classifier import classify_scenes
from app.modules.scene_director.schemas import (
    SceneAnalysisInput,
    SceneClassification,
    SceneDirectorConfig,
    SceneDirectorReport,
)
from app.modules.story import service
from app.modules.story.schemas import StoryRunOut

logger = logging.getLogger(__name__)
router = APIRouter()

# The text providers app.modules.ai.model_router / cost_estimator price
# against. settings.ai_provider is a free string; anything else falls back
# to "anthropic" for the estimate (with a note) rather than raising.
_PRICED_PROVIDERS = ("anthropic", "openai")


# -- config resolution (the Phase 1 "opaque blob" made real) --------------


def resolve_project_config(raw: dict | None) -> ProjectConfig:
    """Validate a Story.project_config_json blob against the real
    ProjectConfig contract. `{}` / None -> every default. A bad blob is a
    400, not a 500.
    """
    try:
        return ProjectConfig.model_validate(raw or {})
    except PydanticValidationError as exc:
        raise ValidationError(f"Story.project_config_json is not a valid ProjectConfig: {exc}") from exc


def build_scene_director_config(pc: ProjectConfig) -> SceneDirectorConfig:
    """Translate the two ProjectConfig sub-configs the Scene Director cares
    about (scene_classification + visual_density.density) into the pure
    module's own config -- the "duplicate the small contract across the
    boundary" convention quality_gate.build_quality_input already follows.
    """
    sc = pc.scene_classification
    return SceneDirectorConfig(
        enabled=sc.enabled,
        w_importance=sc.w_importance,
        w_movement=sc.w_movement,
        w_emotion=sc.w_emotion,
        w_complexity=sc.w_complexity,
        still_motion_threshold=sc.still_motion_threshold,
        video_threshold=sc.video_threshold,
        min_movement_for_video=sc.min_movement_for_video,
        ai_video_max_ratio=sc.ai_video_max_ratio,
        ai_video_hard_cap=sc.ai_video_hard_cap,
        visual_density=pc.visual_density.density,
    )


# -- scene -> SceneAnalysisInput -----------------------------------------


def _scene_inputs(
    chapters_with_scenes: list[tuple[object, list[object]]],
) -> tuple[list[SceneAnalysisInput], dict[str, int]]:
    """Flatten every scene of the story into SceneAnalysisInput, resolving
    prev-scene continuity. Continuity resets at each chapter boundary (a
    per-chapter compile never reuses the previous chapter's last image).

    Returns the inputs and, for each scene, the id of the scene immediately
    before it *within its chapter* (used to fill reuse_asset_from_scene_id
    when the classifier flags a reuse).
    """
    inputs: list[SceneAnalysisInput] = []
    prev_in_chapter: dict[str, int] = {}
    running_order = 0

    for _chapter, scenes in chapters_with_scenes:
        prev = None
        last_index = len(scenes) - 1
        for i, sc in enumerate(scenes):
            running_order += 1
            same_loc = (
                prev is not None
                and sc.location_id is not None
                and sc.location_id == prev.location_id
            )
            same_cast = (
                prev is not None
                and sorted(sc.character_ids_json or []) == sorted(prev.character_ids_json or [])
                and bool(sc.character_ids_json)
            )
            inputs.append(
                SceneAnalysisInput(
                    id=str(sc.id),
                    order=running_order,
                    scene_type=sc.scene_type,
                    narration=sc.narration,
                    dialogue_line_count=len(sc.dialogue_json or []),
                    emotion=sc.emotion,
                    camera=sc.camera,
                    character_count=len(sc.character_ids_json or []),
                    is_chapter_end=(i == last_index),
                    duration_hint=sc.duration_hint,
                    same_location_as_prev=same_loc,
                    same_characters_as_prev=same_cast,
                )
            )
            if prev is not None:
                prev_in_chapter[str(sc.id)] = prev.id
            prev = sc

    return inputs, prev_in_chapter


# -- Scene Director stage ------------------------------------------------


class SceneClassifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: int
    scenes_total: int
    scenes_updated: int
    scenes_frozen: int          # visual_mode_source == "USER", left untouched
    ai_video_count: int
    still_with_motion_count: int
    still_count: int
    reuse_count: int
    demoted_scene_ids: list[str]
    report: SceneDirectorReport


def _persist_updates(
    report: SceneDirectorReport,
    frozen_ids: set[str],
    prev_in_chapter: dict[str, int],
) -> int:
    updates: dict[int, dict] = {}
    for r in report.scenes:
        fields: dict = {
            "importance_score": r.importance_score,
            "emotion_score": r.emotion_score,
            "movement_score": r.movement_score,
            "complexity_score": r.complexity_score,
            "composite_score": r.composite_score,
            "est_cost_usd": _scene_cost(r),
        }
        if r.scene_id not in frozen_ids:
            fields["visual_mode"] = r.visual_mode
            fields["motion_preset"] = r.motion_preset_hint
            fields["reuse_asset_from_scene_id"] = (
                prev_in_chapter.get(r.scene_id) if r.reuse_existing_asset else None
            )
        updates[int(r.scene_id)] = fields
    return service.apply_scene_updates(updates)


def _scene_cost(r: SceneClassification) -> float | None:
    """Per-scene pre-flight cost. A reused still is $0; a generated still /
    still-with-motion is one image; an AI_VIDEO scene is unknown until a
    video provider is priced (Phase 10) -- None, never a fake $0.
    """
    if r.visual_mode == "AI_VIDEO":
        return None
    if r.reuse_existing_asset:
        return 0.0
    return IMAGE_COST_USD


def classify_and_persist(story_id: int) -> SceneClassifyResponse:
    story = service.get_story(story_id)
    pc = resolve_project_config(story.project_config_json)
    cfg = build_scene_director_config(pc)

    tree = service.get_chapters_with_scenes(story_id)
    inputs, prev_in_chapter = _scene_inputs(tree)
    if not inputs:
        raise ValidationError("Story has no scenes to classify yet -- add chapters and scenes first.")

    frozen_ids = {
        str(sc.id)
        for _chap, scenes in tree
        for sc in scenes
        if sc.visual_mode_source == "USER"
    }

    report = classify_scenes(inputs, cfg)
    updated = _persist_updates(report, frozen_ids, prev_in_chapter)

    return SceneClassifyResponse(
        story_id=story_id,
        scenes_total=len(inputs),
        scenes_updated=updated,
        scenes_frozen=len(frozen_ids),
        ai_video_count=report.ai_video_count,
        still_with_motion_count=report.still_with_motion_count,
        still_count=report.still_count,
        reuse_count=report.reuse_count,
        demoted_scene_ids=report.demoted_scene_ids,
        report=report,
    )


# -- pre-flight cost estimate + budget guard -----------------------------

COST_VERDICTS = ("OK", "WARN", "BLOCK", "UNKNOWN")


class StoryCostResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: int
    verdict: str                 # OK | WARN | BLOCK | UNKNOWN
    effective_cap_usd: float | None
    cap_source: str              # "cost_guard" | "story_budget" | "none"
    total_usd: float | None
    estimate: dict               # dataclasses.asdict(CostEstimate)
    scene_counts: dict
    notes: list[str]


def _planning_llm_work(n_chapters: int, n_scenes: int, n_characters: int) -> list[LlmWorkItem]:
    """Conservative buckets for the planning pipeline's LLM calls -- only
    relevant BEFORE any scenes exist. Once the story is planned (or
    imported), these calls never run again.
    """
    return [
        LlmWorkItem("story_development", 1, 2500, 1500),
        LlmWorkItem("story_bible", 1, 3000, 2200),
        LlmWorkItem("character_bible", max(1, n_characters), 1500, 900),
        LlmWorkItem("chapter_outline", 1, 2600, 1800),
        LlmWorkItem("scene_breakdown", max(1, n_chapters), 2600, 2400),
        LlmWorkItem("script", max(1, n_scenes), 900, 700),
    ]


def _produce_llm_work(n_projects: int) -> list[LlmWorkItem]:
    """The only LLM the produce path spends: one AI title/description
    rewrite per compiled Project (Factory PACKAGING stage).
    """
    return [LlmWorkItem("metadata_rewrite", max(1, n_projects), 1200, 400)]


def _word_count(text: str | None) -> int:
    return len((text or "").split())


def build_cost_input(story, tree: list[tuple[object, list[object]]]) -> tuple[CostEstimateInput, dict, list[str]]:
    pc = resolve_project_config(story.project_config_json)
    notes: list[str] = []

    provider = get_settings().ai_provider
    if provider not in _PRICED_PROVIDERS:
        notes.append(f"Provider {provider!r} chưa hỗ trợ ước tính giá LLM -- dùng 'anthropic' để ước tính.")
        provider = "anthropic"

    scenes = [sc for _chap, scenes in tree for sc in scenes]
    n_scenes = len(scenes)
    n_chapters = len(tree)

    # Counts follow the CURRENT persisted visual_mode -- run classify-scenes
    # first for these to reflect the Scene Director's decision.
    new_images = sum(
        1 for sc in scenes
        if sc.visual_mode in ("STILL", "STILL_WITH_MOTION") and sc.reuse_asset_from_scene_id is None
    )
    reused = sum(1 for sc in scenes if sc.reuse_asset_from_scene_id is not None)
    ai_video = [sc for sc in scenes if sc.visual_mode == "AI_VIDEO"]
    ai_video_seconds = sum(sc.duration_hint for sc in ai_video)
    tts_words = sum(_word_count(sc.narration) for sc in scenes)

    scene_counts = {
        "scenes_total": n_scenes,
        "chapters": n_chapters,
        "new_images": new_images,
        "reused_images": reused,
        "ai_video_scenes": len(ai_video),
        "ai_video_seconds": round(ai_video_seconds, 1),
        "narration_words": tts_words,
        "classified": all(sc.composite_score is not None for sc in scenes) if scenes else False,
    }

    # The estimate is forward-looking: "what will producing this story from
    # its CURRENT state cost". Once scenes exist -- whether the pipeline
    # wrote them or they were imported -- the planning LLM calls are done
    # (or will never run), so only the produce-time metadata rewrite counts.
    n_characters = len(service.list_characters(story.id))
    if n_scenes == 0:
        llm_work = _planning_llm_work(n_chapters, n_scenes, n_characters)
    else:
        n_projects = n_chapters if pc.story_compile.compile_mode == "per_chapter" else 1
        llm_work = _produce_llm_work(n_projects)
        notes.append("Kế hoạch đã xong -- LLM ở đây chỉ là bước viết tiêu đề/mô tả lúc produce.")

    inp = CostEstimateInput(
        provider=provider,
        llm_work=llm_work,
        image_count=new_images,
        ai_video_count=len(ai_video),
        ai_video_total_seconds=ai_video_seconds,
        video_provider="null",
        tts_provider=pc.voice.provider,
        tts_word_count=tts_words,
        package_ai_metadata=False,  # rolled into llm_work above
        target_language_count=1,
    )
    return inp, scene_counts, notes


def _guard_verdict(pc: ProjectConfig, story, total: float | None) -> tuple[str, float | None, str]:
    cap = pc.cost_guard.max_total_usd
    cap_source = "cost_guard"
    if cap is None:
        cap = story.budget_usd
        cap_source = "story_budget" if cap is not None else "none"

    if total is None:
        return "UNKNOWN", cap, cap_source
    if cap is None:
        return "OK", None, "none"
    if total > cap:
        return ("BLOCK" if pc.cost_guard.block_on_exceed else "WARN"), cap, cap_source
    if total >= cap * pc.cost_guard.warn_at_fraction:
        return "WARN", cap, cap_source
    return "OK", cap, cap_source


def estimate_cost(story_id: int) -> StoryCostResponse:
    story = service.get_story(story_id)
    pc = resolve_project_config(story.project_config_json)
    tree = service.get_chapters_with_scenes(story_id)

    inp, scene_counts, notes = build_cost_input(story, tree)
    estimate: CostEstimate = estimate_story(inp)
    verdict, cap, cap_source = _guard_verdict(pc, story, estimate.total_usd)

    return StoryCostResponse(
        story_id=story_id,
        verdict=verdict,
        effective_cap_usd=cap,
        cap_source=cap_source,
        total_usd=estimate.total_usd,
        estimate=dataclasses.asdict(estimate),
        scene_counts=scene_counts,
        notes=notes + list(estimate.notes),
    )


# -- read-only combined view for a Studio UI -----------------------------


class ScenePlanRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: int
    chapter_id: int
    order: int
    scene_type: str | None
    visual_mode: str
    visual_mode_source: str
    importance_score: int | None
    emotion_score: int | None
    movement_score: int | None
    complexity_score: int | None
    composite_score: int | None
    est_cost_usd: float | None
    reuse_asset_from_scene_id: int | None
    duration_hint: float


class ScenePlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: int
    scenes: list[ScenePlanRow]
    cost: StoryCostResponse


def scene_plan(story_id: int) -> ScenePlanResponse:
    service.get_story(story_id)  # 404 if missing
    tree = service.get_chapters_with_scenes(story_id)
    rows: list[ScenePlanRow] = []
    running = 0
    for chap, scenes in tree:
        for sc in scenes:
            running += 1
            rows.append(
                ScenePlanRow(
                    scene_id=sc.id,
                    chapter_id=chap.id,
                    order=running,
                    scene_type=sc.scene_type,
                    visual_mode=sc.visual_mode,
                    visual_mode_source=sc.visual_mode_source,
                    importance_score=sc.importance_score,
                    emotion_score=sc.emotion_score,
                    movement_score=sc.movement_score,
                    complexity_score=sc.complexity_score,
                    composite_score=sc.composite_score,
                    est_cost_usd=sc.est_cost_usd,
                    reuse_asset_from_scene_id=sc.reuse_asset_from_scene_id,
                    duration_hint=sc.duration_hint,
                )
            )
    return ScenePlanResponse(story_id=story_id, scenes=rows, cost=estimate_cost(story_id))


# -- the resumable STORY_PLAN run (plan Phase 4) -----------------------
#
# A 1:1 mirror of factory_pipeline._execute_pipeline_sync: a plain daemon
# thread walking a fixed stage list, one StoryCheckpoint per stage, a
# between-stage cancel check, every failure funnelled through
# service.mark_run_failed. There is NO persisted worker -- a run still
# ACTIVE at process start was interrupted (service.reconcile_story_runs_on_startup).

# STORY_PLAN scope: idea -> scenes. VISUAL_PLANNING / COMPILING (turning
# the plan into renderable beat.Project(s)) are plan Phase 5.
_STORY_PLAN_SEQUENCE: tuple[tuple[str, object], ...] = (
    ("STORY_DEVELOPMENT", _stage_story_development),
    ("STORY_BIBLE", _stage_story_bible),
    ("CHARACTER_BIBLE", _stage_character_bible),
    ("CHAPTER_OUTLINE", _stage_chapter_outline),
    ("SCENE_BREAKDOWN", _stage_scene_breakdown),
    # SCENE_CLASSIFICATION is deterministic (Phase 3's classify_and_persist)
    # + the cost-guard gate -- handled inline, not a _stage_* function.
)

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
    service.set_run_fields(run_id, status="CANCELLED", completed_at=service._utcnow())
    return True


def _run_scene_classification_gate(run_id: int, story_id: int) -> None:
    """SCENE_CLASSIFICATION stage: deterministic classify + persist, then
    the pre-flight cost estimate. A BLOCK verdict pauses the run at
    NEEDS_REVIEW (never FAILED) so the user can raise the cap / trim scope
    and retry; WARN/OK/UNKNOWN proceed to READY.
    """
    service.set_run_fields(run_id, status="SCENE_CLASSIFICATION")
    service.start_checkpoint(run_id, "SCENE_CLASSIFICATION")
    t0 = time.monotonic()
    report = classify_and_persist(story_id)
    cost = estimate_cost(story_id)
    service.merge_stage_metrics(run_id, scene_classification_seconds=round(time.monotonic() - t0, 3))
    service.set_run_fields(run_id, est_cost_json=cost.model_dump())

    if cost.verdict == "BLOCK":
        service.complete_checkpoint(run_id, "SCENE_CLASSIFICATION", metadata={
            "ai_video_count": report.ai_video_count, "cost_verdict": cost.verdict,
        })
        service.set_run_fields(
            run_id, status="NEEDS_REVIEW", failed_stage="SCENE_CLASSIFICATION",
            error_code="COST_GUARD_BLOCKED",
            error_message=(
                f"Estimated cost ${cost.total_usd} exceeds the cap "
                f"${cost.effective_cap_usd} ({cost.cap_source}). Raise the budget or trim the story, then retry."
            ),
            requires_human_review=True, review_reason_count=1, completed_at=service._utcnow(),
        )
        return

    service.complete_checkpoint(run_id, "SCENE_CLASSIFICATION", metadata={
        "ai_video_count": report.ai_video_count,
        "still_count": report.still_count,
        "cost_verdict": cost.verdict,
        "est_total_usd": cost.total_usd,
    })
    service.set_run_fields(run_id, status="READY", completed_at=service._utcnow())
    try:
        service.patch_story(story_id, {"status": "SCENES_READY"})
    except Exception:  # noqa: BLE001 -- a story status bump must never fail the run
        logger.exception("story %s: could not set status SCENES_READY", story_id)


def _execute_story_plan_sync(run_id: int, story_id: int, settings: Settings) -> None:
    cancel_event = _cancel_event_for(run_id)
    current_stage = "STORY_DEVELOPMENT"
    try:
        for stage, fn in _STORY_PLAN_SEQUENCE:
            current_stage = stage
            if _bail_if_cancelled(run_id, cancel_event):
                return
            service.set_run_fields(run_id, status=stage)
            service.start_checkpoint(run_id, stage)
            t0 = time.monotonic()
            did_work = fn(story_id, settings)
            service.merge_stage_metrics(run_id, **{f"{stage.lower()}_seconds": round(time.monotonic() - t0, 3)})
            service.complete_checkpoint(run_id, stage, metadata={"generated": bool(did_work)})

        if _bail_if_cancelled(run_id, cancel_event):
            return
        _run_scene_classification_gate(run_id, story_id)
    except StoryStageError as exc:
        service.mark_run_failed(run_id, exc.stage, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001 -- never a raw stack trace to the user
        logger.exception("StoryRun %s failed unexpectedly at %s", run_id, current_stage)
        service.mark_run_failed(run_id, current_stage, "UNEXPECTED_ERROR", str(exc))
    finally:
        _drop_cancel_event(run_id)


def create_and_start_run(story_id: int, settings: Settings) -> object:
    """Start a STORY_PLAN run, or return the story's already-active one
    unchanged (never two at once). Spawns the background thread only for a
    genuinely new run.
    """
    service.get_story(story_id)  # raises NotFoundError if the story is gone
    run, created = service.create_run(story_id, scope="STORY_PLAN")
    if created:
        threading.Thread(
            target=_execute_story_plan_sync, args=(run.id, story_id, settings), daemon=True
        ).start()
    return service.get_run(run.id)


def retry_run(run_id: int, settings: Settings) -> object:
    """Resume a FAILED or cost-guard-paused (NEEDS_REVIEW) run. Replays the
    whole sequence from the top -- every LLM stage's reuse check makes the
    already-done work free, so this naturally resumes from the first
    incomplete stage (same design as factory_pipeline.retry_run).
    """
    run = service.get_run(run_id)
    if run is None:
        raise NotFoundError("StoryRun", run_id)
    if run.status not in ("FAILED", "NEEDS_REVIEW"):
        raise ValidationError(
            f"Only a FAILED or NEEDS_REVIEW run can be retried (this run is {run.status})."
        )
    service.increment_attempt(run_id)
    service.set_run_fields(
        run_id, status="STORY_DEVELOPMENT", error_code=None, error_message=None,
        failed_stage=None, completed_at=None, requires_human_review=run.requires_human_review,
    )
    threading.Thread(
        target=_execute_story_plan_sync, args=(run_id, run.story_id, settings), daemon=True
    ).start()
    return service.get_run(run_id)


def cancel_run(run_id: int) -> object:
    """Signal a cooperative cancel -- the background thread stops at the
    next stage boundary (a stage mid-LLM-call can't be force-killed, same
    as factory_pipeline.cancel_run's own local stages).
    """
    run = service.get_run(run_id)
    if run is None:
        raise NotFoundError("StoryRun", run_id)
    if run.status in ("COMPLETED", "FAILED", "CANCELLED", "READY"):
        return run
    _cancel_event_for(run_id).set()
    return service.get_run(run_id)


# -- routes -------------------------------------------------------------


@router.get("/stories/{story_id}/config", response_model=ProjectConfig)
def get_resolved_config(story_id: int) -> ProjectConfig:
    story = service.get_story(story_id)
    return resolve_project_config(story.project_config_json)


@router.post("/stories/{story_id}/classify-scenes", response_model=SceneClassifyResponse)
def classify_story_scenes(story_id: int) -> SceneClassifyResponse:
    return classify_and_persist(story_id)


@router.get("/stories/{story_id}/cost-estimate", response_model=StoryCostResponse)
def get_cost_estimate(story_id: int) -> StoryCostResponse:
    return estimate_cost(story_id)


@router.get("/stories/{story_id}/scene-plan", response_model=ScenePlanResponse)
def get_scene_plan(story_id: int) -> ScenePlanResponse:
    return scene_plan(story_id)


def _run_out(run) -> StoryRunOut:
    return StoryRunOut.model_validate(run, from_attributes=True)


@router.post("/stories/{story_id}/runs", response_model=StoryRunOut, status_code=201)
def start_story_run(story_id: int, settings: Settings = Depends(get_settings)) -> StoryRunOut:
    """Start (or reuse) a STORY_PLAN run: STORY_DEVELOPMENT -> ... ->
    SCENE_BREAKDOWN -> SCENE_CLASSIFICATION + cost guard. Runs on a
    background thread; poll GET /story-runs/{id}.
    """
    return _run_out(create_and_start_run(story_id, settings))


@router.post("/story-runs/{run_id}/retry", response_model=StoryRunOut)
def retry_story_run(run_id: int, settings: Settings = Depends(get_settings)) -> StoryRunOut:
    return _run_out(retry_run(run_id, settings))


@router.post("/story-runs/{run_id}/cancel", response_model=StoryRunOut)
def cancel_story_run(run_id: int) -> StoryRunOut:
    return _run_out(cancel_run(run_id))
