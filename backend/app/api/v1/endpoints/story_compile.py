"""AI Storytelling Studio -- compile a planned Story into renderable
beat.Project(s) and hand each off to the Factory (plan Phase 5, the last
phase of the technical path).

Composition root: like story_pipeline.py / factory_pipeline.py this file is
core HTTP infrastructure, not a module, so it may import app.modules.story
+ app.modules.beat + app.modules.factory together and stitch them. It
implements NO new render pipeline -- COMPILING builds a BeatPlan per the
StoryCompileProjectConfig and creates the Project rows; PRODUCING then
delegates each Project to factory_pipeline.create_and_start_run (the exact
same path the Video Factory button uses).

  POST /stories/{id}/produce  -- compile + start a Factory run per Project
  GET  /stories/{id}/compiled -- the compiled Project(s) + their Factory run

The Story's own PRODUCE StoryRun finishes once every Project is compiled
and handed off; the renders themselves are then tracked as FactoryRuns
(visible in Video Factory and in GET /stories/{id}/compiled).
"""

from __future__ import annotations

import logging
import threading
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.api.v1.endpoints.factory_pipeline import create_and_start_run as start_factory_run
from app.api.v1.endpoints.factory_pipeline import get_video_composer_service
from app.api.v1.endpoints.story_pipeline import (
    _bail_if_cancelled,
    _cancel_event_for,
    _drop_cancel_event,
    estimate_cost,
    resolve_project_config,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import SessionLocal
from app.modules.beat.models import Project
from app.modules.beat.project_service import unique_project_slug
from app.modules.beat.schemas import MAX_DURATION, MIN_DURATION, Beat, BeatMotionPreset, BeatPlan, BeatType
from app.modules.factory import service as factory_service
from app.modules.story import service
from app.modules.story.schemas import StoryRunOut
from app.modules.video_composer.service import VideoComposerService

logger = logging.getLogger(__name__)
router = APIRouter()

# Story scene type -> the closest beat.BeatType (Beat's set is smaller).
_SCENE_TYPE_TO_BEAT: dict[str, str] = {
    "HOOK": "HOOK",
    "SETUP": "SETUP",
    "BUILD": "BUILD",
    "REVEAL": "REVEAL",
    "CLIMAX": "REVEAL",
    "TWIST": "REVEAL",
    "REACTION": "REACTION",
    "CONFRONTATION": "REACTION",
    "TRANSITION": "BODY",
    "ENDING": "ENDING",
    "BODY": "BODY",
}
_VALID_MOTION = {m.value for m in BeatMotionPreset}


def _clamp_duration(value: float) -> float:
    try:
        return round(max(MIN_DURATION, min(MAX_DURATION, float(value))), 2)
    except (TypeError, ValueError):
        return 6.0


def _style_summary(style_bible: dict) -> str:
    parts = [
        style_bible.get("palette"),
        style_bible.get("lighting"),
        style_bible.get("mood"),
    ]
    refs = style_bible.get("visual_references") or []
    text = ", ".join(p for p in parts if p)
    if refs:
        text = f"{text}; references: {', '.join(str(r) for r in refs[:3])}" if text else ", ".join(str(r) for r in refs[:3])
    return text


def _visual_description(scene, chars_by_id: dict, locs_by_id: dict) -> str | None:
    """The showable per-beat image description. Every character on screen
    contributes their LOCKED canonical_prompt_block verbatim -- that is the
    character-consistency mechanism (the same block in every scene's prompt).
    """
    parts: list[str] = []
    base = (scene.image_prompt or "").strip() or (scene.narration or "").strip()
    if base:
        parts.append(base[:400])
    for cid in scene.character_ids_json or []:
        ch = chars_by_id.get(cid)
        if ch and ch.canonical_prompt_block:
            parts.append(ch.canonical_prompt_block.strip())
    loc = locs_by_id.get(scene.location_id)
    if loc and loc.description:
        parts.append(f"Setting: {loc.description.strip()}")
    if scene.time_of_day:
        parts.append(scene.time_of_day.strip())
    text = ". ".join(p.rstrip(".") for p in parts if p)
    return text or None


def _scene_to_raw_beat(scene, chars_by_id: dict, locs_by_id: dict) -> dict:
    beat_type = _SCENE_TYPE_TO_BEAT.get((scene.scene_type or "").upper(), "BODY")
    mp = scene.motion_preset if scene.motion_preset in _VALID_MOTION else None
    # Keep only a *deliberate* content-driven preset (STATIC for a text/quote
    # beat, SLOW_PULL_OUT for a wide establish, ZOOM_AND_PAN for a pan/action
    # scene). The Scene Director's generic SLOW_PUSH_IN fallback is dropped so
    # auto_rotate (below) cycles the whole pool -- 10 minutes of identical
    # push-ins reads as a template and tanks retention.
    if mp == "SLOW_PUSH_IN":
        mp = None
    return {
        "type": beat_type,
        "narration": (scene.narration or "").strip() or None,
        "duration": _clamp_duration(scene.duration_hint),
        "visual_description": _visual_description(scene, chars_by_id, locs_by_id),
        "visual_hint": ((scene.image_prompt or "").strip()[:60] or None),
        "motion_preset": mp,
        "camera": scene.camera or None,
        "lighting": scene.lighting or None,
        "emotion": scene.emotion or None,
        "time_of_day": scene.time_of_day or None,
        "continuity_notes": scene.continuity_notes or None,
    }


def _merge_short(raw: list[dict], threshold: float) -> list[dict]:
    """Fold a scene shorter than `threshold` into the one before it (each
    scene is a separately-billed image) -- backward only, never merging a
    short opening beat. Mirrors beat_generate._merge_short_beats.
    """
    if threshold <= 0 or len(raw) <= 2:
        return raw
    merged: list[dict] = [dict(raw[0])]
    for item in raw[1:]:
        prev = merged[-1]
        if item["duration"] < threshold and prev["duration"] + item["duration"] <= MAX_DURATION:
            prev["narration"] = " ".join(
                t for t in [(prev.get("narration") or "").strip(), (item.get("narration") or "").strip()] if t
            ) or None
            if not prev.get("visual_description"):
                prev["visual_description"] = item.get("visual_description")
            prev["duration"] = round(prev["duration"] + item["duration"], 2)
        else:
            merged.append(dict(item))
    return merged if len(merged) >= 2 else raw


def _beats_from_raw(raw: list[dict]) -> list[Beat]:
    return [
        Beat(
            id=f"scene_{i + 1:03d}",
            order=i + 1,
            type=BeatType(item["type"]),
            narration=item.get("narration"),
            duration=item["duration"],
            visual_hint=item.get("visual_hint"),
            visual_description=item.get("visual_description"),
            motion_preset=BeatMotionPreset(item["motion_preset"]) if item.get("motion_preset") else None,
            camera=item.get("camera"),
            lighting=item.get("lighting"),
            emotion=item.get("emotion"),
            time_of_day=item.get("time_of_day"),
            continuity_notes=item.get("continuity_notes"),
        )
        for i, item in enumerate(raw)
    ]


def _build_beat_plan(
    story, pc, scenes: list, chars_by_id: dict, locs_by_id: dict, project_name: str,
    *, render_profile: str | None = None,
) -> BeatPlan:
    raw = [_scene_to_raw_beat(sc, chars_by_id, locs_by_id) for sc in scenes]
    raw = _merge_short(raw, pc.story_compile.merge_scenes_under_seconds)
    beats = _beats_from_raw(raw)

    config = pc.model_copy(deep=True)
    if render_profile is not None:
        config.render = config.render.model_copy(update={"profile": render_profile})
    config.audio = config.audio.model_copy(update={"narration_enabled": True})
    config.visual_generation = config.visual_generation.model_copy(update={
        "mode": "ai_generated",
        "image_style_prompt": _style_summary(story.style_bible_json or {}) or config.visual_generation.image_style_prompt,
    })
    # The story bible's tone drives BGM auto-selection
    # (audio.service.select_bgm matches config.content.tone against its tone
    # rules) and the image-prompt tone derivation. A generic default would
    # give a horror story the same soft-piano track as a romance.
    bible_tone = (story.story_bible_json or {}).get("tone")
    style_mood = (story.style_bible_json or {}).get("mood")
    tone = ", ".join(t for t in (bible_tone, style_mood) if t)
    if tone:
        config.content = config.content.model_copy(update={"tone": tone})

    # A story is narrated published content -- the offline SAPI5 "local"
    # voice reads as robotic. Default to edge_tts (free, networked, the
    # voice the caption engine locks to) unless the story's own config
    # explicitly chose a provider.
    if "provider" not in (story.project_config_json.get("voice") or {}):
        config.voice = config.voice.model_copy(update={"provider": "edge_tts"})

    # Ken-Burns variety: cycle the motion pool for any beat without a
    # deliberate content-driven preset (see _scene_to_raw_beat) -- 10
    # minutes of identical slow push-ins reads as a template.
    config.motion = config.motion.model_copy(update={
        "auto_rotate": True,
        "default_preset": BeatMotionPreset.SLOW_PUSH_IN,
    })

    # A closing segment so the video doesn't cut dead on the last narrated
    # word (a fixed string, never per-story AI text). Language follows the
    # narration; a story that set its own outro text wins.
    if not (story.project_config_json.get("outro") or {}).get("text"):
        lang = (config.voice.language or "en").split("-")[0].lower()
        config.outro = config.outro.model_copy(update={
            "enabled": True,
            "text": (
                "Cảm ơn đã xem. Đăng ký kênh để không bỏ lỡ tập tiếp theo."
                if lang == "vi"
                else "Thanks for watching. Subscribe for the next one."
            ),
        })

    script_text = "\n\n".join(b.narration for b in beats if b.narration) or None
    return BeatPlan(
        script_text=script_text, beats=beats, project_name=project_name, config=config, script_locked=True,
    )


# -- compile ----------------------------------------------------------


class CompiledProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int
    chapter_id: int | None
    label: str
    beat_count: int
    reused: bool


class CompileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: int
    compile_mode: str
    projects: list[CompiledProject]


def _create_project(name: str, plan: BeatPlan) -> int:
    db = SessionLocal()
    try:
        project = Project(name=name, slug=unique_project_slug(name, db), beat_plan_json=plan.model_dump(mode="json"))
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


def _project_exists(project_id: int | None) -> bool:
    if project_id is None:
        return False
    db = SessionLocal()
    try:
        return db.get(Project, project_id) is not None
    finally:
        db.close()


def _reusable_project(project_id: int | None, want_profile: str) -> tuple[bool, int]:
    """(reuse?, beat_count) for an already-compiled project. Not reusable if
    it's gone or its render profile no longer matches the story's config
    (e.g. the user switched 9:16 -> 16:9) -- then it must be recompiled.
    """
    if project_id is None:
        return False, 0
    db = SessionLocal()
    try:
        p = db.get(Project, project_id)
        if p is None:
            return False, 0
        cfg = (p.beat_plan_json or {}).get("config", {})
        profile = (cfg.get("render") or {}).get("profile")
        beat_count = len((p.beat_plan_json or {}).get("beats", []))
        return profile == want_profile, beat_count
    finally:
        db.close()


# A "test" produce: the first few scenes only -- a quick, ~$0.02 look at
# the character / voice / pacing before committing to the whole story.
_TEST_MAX_SCENES = 5


def _test_render_profile(story_profile: str) -> str:
    """Preview a 9:16 story at the small PREVIEW profile; a 16:9 story has
    no small landscape profile, so test-render it at its real profile
    (still cheap -- only 5 scenes).
    """
    return "PREVIEW" if story_profile == "SOCIAL_VERTICAL" else story_profile


def compile_story(story_id: int, *, test: bool = False) -> CompileResult:
    story = service.get_story(story_id)
    pc = resolve_project_config(story.project_config_json)
    tree = service.get_chapters_with_scenes(story_id)
    if not tree or all(len(sc) == 0 for _c, sc in tree):
        raise ValidationError("This story has no scenes to compile -- run the planning pipeline first.")

    chars_by_id = {c.id: c for c in service.list_characters(story_id)}
    locs_by_id = {loc.id: loc for loc in service.list_locations(story_id)}
    mode = pc.story_compile.compile_mode
    projects: list[CompiledProject] = []

    if test:
        # First N scenes, one throwaway Project, never linked to a chapter
        # / episode (a real Produce still compiles the full thing fresh).
        all_scenes = [sc for _c, scenes in tree for sc in scenes][:_TEST_MAX_SCENES]
        name = f"{story.title} — TEST"
        plan = _build_beat_plan(
            story, pc, all_scenes, chars_by_id, locs_by_id, name,
            render_profile=_test_render_profile(pc.render.profile),
        )
        pid = _create_project(name, plan)
        return CompileResult(
            story_id=story_id, compile_mode="test",
            projects=[CompiledProject(
                project_id=pid, chapter_id=None, label=f"Test ({len(plan.beats)} scenes)",
                beat_count=len(plan.beats), reused=False,
            )],
        )

    if mode == "per_chapter":
        for chapter, scenes in tree:
            if not scenes:
                continue
            reuse, beat_count = _reusable_project(chapter.compiled_project_id, pc.render.profile)
            if reuse:
                projects.append(CompiledProject(
                    project_id=chapter.compiled_project_id, chapter_id=chapter.id,
                    label=chapter.title or f"Chapter {chapter.order}", beat_count=beat_count, reused=True,
                ))
                continue
            name = f"{story.title} — {chapter.order}. {chapter.title or 'Chapter'}"
            plan = _build_beat_plan(story, pc, scenes, chars_by_id, locs_by_id, name)
            pid = _create_project(name, plan)
            service.set_chapter_compiled_project(chapter.id, pid)
            projects.append(CompiledProject(
                project_id=pid, chapter_id=chapter.id, label=chapter.title or f"Chapter {chapter.order}",
                beat_count=len(plan.beats), reused=False,
            ))
    else:  # single
        all_scenes = [sc for _c, scenes in tree for sc in scenes]
        existing = story.episode_id and service.get_episode(story.episode_id).compiled_project_ids_json
        reuse_checks = [_reusable_project(pid, pc.render.profile) for pid in existing] if existing else []
        if reuse_checks and all(ok for ok, _ in reuse_checks):
            for pid, (_, beat_count) in zip(existing, reuse_checks):
                projects.append(CompiledProject(
                    project_id=pid, chapter_id=None, label=story.title, beat_count=beat_count, reused=True,
                ))
        else:
            plan = _build_beat_plan(story, pc, all_scenes, chars_by_id, locs_by_id, story.title)
            pid = _create_project(story.title, plan)
            if story.episode_id:
                service.set_episode_compiled_projects(story.episode_id, [pid])
            projects.append(CompiledProject(
                project_id=pid, chapter_id=None, label=story.title, beat_count=len(plan.beats), reused=False,
            ))

    return CompileResult(story_id=story_id, compile_mode=mode, projects=projects)


# -- the PRODUCE run ------------------------------------------------


def _execute_story_produce_sync(
    run_id: int, story_id: int, settings: Settings, service_vc: VideoComposerService, *, test: bool = False
) -> None:
    cancel_event = _cancel_event_for(run_id)
    try:
        # COMPILING -- reuse the run's own recorded ids on a retry.
        service.set_run_fields(run_id, status="COMPILING")
        service.start_checkpoint(run_id, "COMPILING")
        t0 = time.monotonic()

        run = service.get_run(run_id)
        prior = run.compiled_project_ids_json if run else []
        want_profile = resolve_project_config(service.get_story(story_id).project_config_json).render.profile
        if prior and all(_reusable_project(pid, want_profile)[0] for pid in prior):
            project_ids = list(prior)
        else:
            result = compile_story(story_id, test=test)
            project_ids = [p.project_id for p in result.projects]
            service.set_run_fields(run_id, compiled_project_ids_json=project_ids)
        service.merge_stage_metrics(run_id, compiling_seconds=round(time.monotonic() - t0, 3))
        service.complete_checkpoint(run_id, "COMPILING", metadata={"project_ids": project_ids, "test": test})

        if _bail_if_cancelled(run_id, cancel_event):
            return

        # PRODUCING -- hand each Project to the Factory (its own thread).
        service.set_run_fields(run_id, status="PRODUCING")
        service.start_checkpoint(run_id, "PRODUCING")
        started = 0
        for pid in project_ids:
            try:
                start_factory_run(pid, settings, service_vc)
                started += 1
            except Exception:  # noqa: BLE001 -- one project failing to start must not abort the rest
                logger.exception("story produce: could not start a factory run for project %s", pid)
        service.complete_checkpoint(run_id, "PRODUCING", metadata={"factory_runs_started": started, "test": test})

        service.set_run_fields(run_id, status="COMPLETED", completed_at=service._utcnow())
        if not test:
            try:
                service.patch_story(story_id, {"status": "PRODUCING"})
            except Exception:  # noqa: BLE001
                logger.exception("story %s: could not set status PRODUCING", story_id)
    except ValidationError as exc:
        service.mark_run_failed(run_id, "COMPILING", "COMPILE_FAILED", str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Story PRODUCE run %s failed unexpectedly", run_id)
        service.mark_run_failed(run_id, "COMPILING", "UNEXPECTED_ERROR", str(exc))
    finally:
        _drop_cancel_event(run_id)


def produce_story(story_id: int, settings: Settings, service_vc: VideoComposerService, *, test: bool = False):
    story = service.get_story(story_id)
    tree = service.get_chapters_with_scenes(story_id)
    if not tree or all(len(sc) == 0 for _c, sc in tree):
        raise ValidationError("This story has no scenes to compile -- run the planning pipeline first.")

    # A test render is a handful of scenes -- never blocked by the cost cap
    # (its whole point is to be cheap); a full produce still is.
    if not test:
        cost = estimate_cost(story_id)
        if cost.verdict == "BLOCK":
            raise ValidationError(
                f"Estimated cost ${cost.total_usd} exceeds the cap ${cost.effective_cap_usd} ({cost.cap_source}). "
                "Raise the budget or trim the story before producing."
            )

    run, created = service.create_run(story_id, scope="PRODUCE")
    if created:
        threading.Thread(
            target=_execute_story_produce_sync, args=(run.id, story_id, settings, service_vc),
            kwargs={"test": test}, daemon=True,
        ).start()
    return service.get_run(run.id)


def _factory_run_dict(project_id: int) -> dict | None:
    fr = factory_service.get_latest_run_for_project(project_id)
    if fr is None:
        return None
    return {
        "id": fr.id, "status": fr.status, "failed_stage": fr.failed_stage,
        "error_message": fr.error_message, "render_job_id": fr.render_job_id,
    }


def _compiled_view(story_id: int) -> list[dict]:
    service.get_story(story_id)  # 404
    out: list[dict] = []
    seen: set[int] = set()

    for chapter in service.list_chapters(story_id):
        if chapter.compiled_project_id is None:
            continue
        seen.add(chapter.compiled_project_id)
        out.append({
            "project_id": chapter.compiled_project_id,
            "chapter_id": chapter.id,
            "label": chapter.title or f"Chapter {chapter.order}",
            "is_test": False,
            "factory_run": _factory_run_dict(chapter.compiled_project_id),
        })

    # The latest PRODUCE run's own projects -- covers `single` compile mode
    # and, crucially, a test render (never linked to a chapter).
    runs = [r for r in service.list_runs_for_story(story_id) if r.scope == "PRODUCE"]
    if runs:
        latest = runs[0]
        is_test = any(
            (c.checkpoint_metadata_json or {}).get("test")
            for c in service.get_checkpoints(latest.id)
        )
        for pid in latest.compiled_project_ids_json or []:
            if pid in seen or not _project_exists(pid):
                continue
            seen.add(pid)
            out.append({
                "project_id": pid, "chapter_id": None,
                "label": "Test render" if is_test else "Full story",
                "is_test": is_test,
                "factory_run": _factory_run_dict(pid),
            })
    return out


# -- routes -------------------------------------------------------------


class CompiledResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_id: int
    projects: list[dict]


@router.post("/stories/{story_id}/produce", response_model=StoryRunOut, status_code=201)
def produce_story_endpoint(
    story_id: int,
    test: bool = False,
    settings: Settings = Depends(get_settings),
    service_vc: VideoComposerService = Depends(get_video_composer_service),
) -> StoryRunOut:
    """`?test=true` compiles only the first few scenes at the PREVIEW
    profile -- a quick, cheap look before the full produce.
    """
    run = produce_story(story_id, settings, service_vc, test=test)
    return StoryRunOut.model_validate(run, from_attributes=True)


@router.get("/stories/{story_id}/compiled", response_model=CompiledResponse)
def get_compiled(story_id: int) -> CompiledResponse:
    return CompiledResponse(story_id=story_id, projects=_compiled_view(story_id))
