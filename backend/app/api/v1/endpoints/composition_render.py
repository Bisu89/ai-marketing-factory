"""The adapter boundary between the Video Factory contracts
(app.modules.composition / app.modules.motion) and the existing
app.modules.video_composer renderer -- see
docs/features/24-composition-video-composer-integration.md.

Per app/modules/README.md, no module may import another module.
`app.modules.video_composer` must not import `app.modules.motion`,
`app.modules.asset`, or `app.modules.beat`; `app.modules.composition` must
not import `app.modules.motion` or `app.modules.video_composer` either.
Something has to translate a CompositionPlan's Scenes into calls against
both the motion renderer and video_composer's job API, and per this
codebase's established "composition root" convention (the only place
`app/main.py` and `app/api/v1/router.py` are allowed to know about
multiple modules at once -- see app/modules/README.md), that translation
lives here: `app/api/v1/endpoints/*` is core HTTP-layer infrastructure,
not a module under app/modules/, so it may import all three.

`render_composition()` is the actual adapter logic (video_composer stays
completely unaware this file exists); `create_video_compose_job_from_composition`
is a thin HTTP wrapper around it, matching this app's own convention that
endpoint handlers "parse request, call service, map response" with no
business logic of their own (see docs/architecture.md).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import FileOperationError, NotFoundError, ValidationError
from app.core.render_policy import enforce_local_rendering_policy
from app.db.session import get_db
from app.modules.composition.schemas import CompositionPlan, Scene, SceneMotion
from app.modules.motion.renderer import render_motion_clip
from app.modules.motion.schemas import Easing as MotionEasing
from app.modules.motion.schemas import MotionPlan, MotionPresetName
from app.modules.motion.schemas import PositionRange as MotionPositionRange
from app.modules.motion.schemas import RotationRange as MotionRotationRange
from app.modules.motion.schemas import ScaleRange as MotionScaleRange
from app.modules.video_composer.models import VideoComposeJob
from app.modules.video_composer.schemas import VideoComposeJobOut, job_to_out
from app.modules.video_composer.service import VideoComposerService

router = APIRouter()

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}

# video_composer's own Form default for transition_duration (see
# app/modules/video_composer/router.py's create_video_compose_job) --
# reused here as the fallback when a CompositionPlan has nothing usable to
# derive one from.
_DEFAULT_TRANSITION_DURATION = 0.5


def _is_image_path(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


def _scene_motion_to_motion_plan(scene_motion: SceneMotion, duration: float) -> MotionPlan:
    """Converts Composition's own, deliberately-duplicated SceneMotion shape
    (see app/modules/composition/schemas.py's module docstring for why it's
    a duplicate, not an import, of Motion's MotionPlan) into a real
    MotionPlan the renderer accepts. This conversion is exactly what an
    adapter is for -- neither module is allowed to do it itself.
    """
    try:
        preset = MotionPresetName(scene_motion.preset_name)
    except ValueError:
        # preset_name is a free-form, unvalidated label on the Composition
        # side (see 22-composition-contract.md) -- it may be absent or not
        # match any real Motion preset. The renderer never branches on
        # `.preset` (see 23-local-motion-renderer.md), so any valid member
        # works here; this only affects a log line, never the rendered
        # output, which is driven entirely by the numeric fields below.
        preset = MotionPresetName.ZOOM_AND_PAN

    return MotionPlan(
        preset=preset,
        duration=duration,
        scale=MotionScaleRange(start=scene_motion.scale.start, end=scene_motion.scale.end),
        position=MotionPositionRange(
            x_start=scene_motion.position.x_start,
            y_start=scene_motion.position.y_start,
            x_end=scene_motion.position.x_end,
            y_end=scene_motion.position.y_end,
        ),
        rotation=MotionRotationRange(start=scene_motion.rotation.start, end=scene_motion.rotation.end),
        easing=MotionEasing(scene_motion.easing.value),
    )


def _compute_scene_start_times(scenes: list[Scene], transition_duration: float) -> dict[str, float]:
    """Approximates each Scene's start offset within the final merged
    video, using the exact same cumulative-duration-minus-overlap formula
    `video_composer.service._merge_clips_with_transitions` itself uses
    (shortest-clip-clamped `safe_transition`, then running `cumulative`) --
    reproduced here, not imported, since it's a handful of arithmetic lines
    on primitive floats, not a reason to reach into a private method.
    Uses each Scene's requested `duration` rather than a post-render probed
    duration, since this only needs to be good enough to place an SFX cue
    at roughly the right moment, not frame-accurate.
    """
    if not scenes:
        return {}
    shortest = min(scene.duration for scene in scenes)
    safe_transition = min(transition_duration, shortest / 2)

    starts: dict[str, float] = {scenes[0].id: 0.0}
    cumulative = scenes[0].duration
    for scene in scenes[1:]:
        starts[scene.id] = max(0.0, cumulative - safe_transition)
        cumulative = cumulative + scene.duration - safe_transition
    return starts


def _build_sfx_cues(scenes: list[Scene], transition_duration: float) -> list[dict]:
    """Every Scene with a non-null `audio.sfx` becomes one SFX cue timed to
    that scene's approximate start offset -- see
    `VideoComposerService._mix_audio`'s `sfx_cues` parameter.
    """
    starts = _compute_scene_start_times(scenes, transition_duration)
    return [
        {"path": scene.audio.sfx, "start_sec": starts[scene.id], "volume": scene.audio.sfx_volume}
        for scene in scenes
        if scene.audio.sfx
    ]


def _derive_transition_duration(scenes: list[Scene]) -> float:
    """video_composer only supports one uniform transition duration for an
    entire job (see app/modules/video_composer/service.py's
    _merge_clips_with_transitions) -- extending it to honor each Scene's own
    SceneTransition.duration/.type individually would mean rewriting that
    method's loop, which is explicitly out of scope ("do NOT rewrite the
    existing composer"). Averaging the durations of scenes that actually
    participate in a transition (order > 1 -- the first scene has nothing
    to transition from) is a deliberate, documented simplification, not an
    oversight; SceneTransition.type is not honored at all yet (every merge
    still uses video_composer's fixed "slideleft" style regardless of what
    a Scene requests). See docs/features/24-composition-video-composer-integration.md.
    """
    real_transitions = [scene.transition.duration for scene in scenes if scene.order > 1]
    if not real_transitions:
        return _DEFAULT_TRANSITION_DURATION
    return sum(real_transitions) / len(real_transitions)


def render_composition(
    plan: CompositionPlan,
    asset_paths: dict[int, str],
    service: VideoComposerService,
    title: str = "Composition",
    output_dir: str | None = None,
) -> int:
    """Turns a CompositionPlan into a running VideoComposeJob.

    Renders each image-backed Scene into a clip via app.modules.motion's
    renderer (Task 06); a Scene whose asset is already a video clip is
    passed straight through, untouched. The resulting ordered clip list is
    handed to video_composer's EXISTING, UNMODIFIED merge/narrate/subtitle/
    mix/finalize pipeline via the new `VideoComposerService.save_clip_paths`
    -- nothing about that pipeline changes for this new entry point.

    `asset_paths` maps each Scene.source_asset_id to a real filesystem path.
    Resolving that mapping (e.g. by querying app.modules.asset) is
    deliberately the caller's responsibility, not this function's -- it
    keeps this adapter's own dependency surface to exactly the three
    modules this integration is about (composition, motion, video_composer),
    matching this task's "smallest safe change" instruction rather than
    also wiring in Asset lookups that weren't asked for.
    """
    enforce_local_rendering_policy()

    if not plan.scenes:
        raise ValidationError("CompositionPlan has no scenes to render")

    transition_duration = _derive_transition_duration(plan.scenes)
    sfx_cues = _build_sfx_cues(plan.scenes, transition_duration)

    job_id = service.create_job(
        title=title,
        script_text=plan.narration_script or "",
        voice=plan.voice,
        music_volume=plan.music_volume,
        transition_duration=transition_duration,
        burn_subtitles=True,
        requested_output_dir=output_dir,
        narration_volume=plan.narration_volume,
        music_ducking_ratio=plan.music_ducking_ratio,
        fade_in_sec=plan.fade_in_sec,
        fade_out_sec=plan.fade_out_sec,
        caption_preset=plan.caption_preset.value,
        sfx_cues=sfx_cues or None,
    )
    if plan.music_path:
        service.set_music_path(job_id, plan.music_path)

    scenes_dir = service.job_dir(job_id) / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    clip_paths: list[Path] = []
    for scene in plan.ordered_scenes():
        raw_path = asset_paths.get(scene.source_asset_id)
        if raw_path is None:
            raise ValidationError(
                f"No asset path provided for scene {scene.id!r} (asset_id={scene.source_asset_id})"
            )
        source_path = Path(raw_path)
        if not source_path.exists():
            raise FileOperationError(f"Asset file not found for scene {scene.id!r}: {source_path}")

        if _is_image_path(source_path):
            motion_plan = _scene_motion_to_motion_plan(scene.motion, scene.duration)
            output_clip = scenes_dir / f"{scene.id}.mp4"
            render_motion_clip(
                source_path,
                motion_plan,
                output_clip,
                duration=scene.duration,
                fps=scene.output_format.fps,
                width=scene.output_format.width,
                height=scene.output_format.height,
            )
            clip_paths.append(output_clip)
        else:
            clip_paths.append(source_path)

    service.save_clip_paths(job_id, clip_paths)
    service.enqueue(job_id)
    return job_id


class CompositionRenderRequest(BaseModel):
    plan: CompositionPlan
    asset_paths: dict[int, str]
    title: str = "Composition"
    output_dir: str | None = None


def get_video_composer_service(request: Request) -> VideoComposerService:
    return request.app.state.video_composer_service


@router.post("/video-compose-jobs/from-composition", response_model=VideoComposeJobOut, status_code=201)
def create_video_compose_job_from_composition(
    payload: CompositionRenderRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    service: VideoComposerService = Depends(get_video_composer_service),
):
    job_id = render_composition(payload.plan, payload.asset_paths, service, payload.title, payload.output_dir)
    job = (
        db.query(VideoComposeJob)
        .options(selectinload(VideoComposeJob.clips))
        .filter(VideoComposeJob.id == job_id)
        .first()
    )
    if job is None:
        raise NotFoundError("Video compose job", job_id)
    return job_to_out(job, Path(settings.library_dir))
