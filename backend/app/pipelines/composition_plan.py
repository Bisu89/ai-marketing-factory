"""Project BeatPlan -> renderable CompositionPlan, for the Factory pipeline's
RENDER stage (see factory_stages._stage_render).

A composition root like the rest of app/pipelines/: it imports
app.modules.asset (resolving a Beat's asset_id -> a real file path),
app.modules.motion (resolving a motion preset -> numeric render
parameters) and app.modules.composition, none of which may import each
other. Moved here unchanged from the removed batch_render.py (see
docs/features/157-remove-unused-features.md), which used to own it.
"""

from pathlib import Path

from app.api.v1.endpoints.motion_generate import resolve_effective_preset
from app.core.exceptions import FileOperationError, ValidationError
from app.core.render_profile import get_render_profile
from app.modules.asset.service import AssetService
from app.modules.beat.schemas import BeatPlan
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

_DEFAULT_TRANSITION_DURATION = 0.4


def beat_to_scene(beat, config, output_format: OutputFormat) -> Scene:
    # Task 23 (see docs/features/49-local-motion-engine.md sections 8/29/58)
    # -- manual Beat.motion_preset > deterministic auto-rotation (only when
    # the project opted into MotionProjectConfig.auto_rotate) > the fixed
    # project default. Every unset beat silently reusing the exact same
    # default_preset is the "every beat = zoom in" outcome section 29
    # explicitly calls out.
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
    frontend/src/pages/VideoFactoryPage.tsx, needed because a Factory run
    has no human stepping through the wizard. Raises
    ValidationError/NotFoundError/FileOperationError (never returns a
    partially-valid plan).
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
