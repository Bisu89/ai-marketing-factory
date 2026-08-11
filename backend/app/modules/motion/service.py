"""Motion planning: resolves a named preset (e.g. "slow_push_in") into a
fully-parameterized MotionPlan. Pure and deterministic -- the same preset
(and duration override, if given) always produces an equal plan, with no
randomness, no I/O, and no external state.

Deliberately contains no ffmpeg/subprocess/rendering code of any kind, and
no filesystem or database access -- this module only plans motion, per the
task's "does NOT render video" boundary. A future rendering layer consumes
the MotionPlan this produces; it is not part of this module and this
module must never import it.
"""

from app.modules.motion.schemas import (
    Easing,
    MotionPlan,
    MotionPresetName,
    PositionRange,
    RotationRange,
    ScaleRange,
)

_CENTER = PositionRange(x_start=0.5, y_start=0.5, x_end=0.5, y_end=0.5)
_NO_ROTATION = RotationRange(start=0.0, end=0.0)

# Default duration for every preset. A specific beat's actual on-screen
# time is Beat's concern (see app/modules/beat/schemas.py's Beat.duration),
# not Motion's -- this is only the fallback used when a caller doesn't ask
# for a different duration via build_motion_plan(duration=...). 4 seconds
# also matches the task brief's own slow_push_in example.
_DEFAULT_DURATION = 4.0


def _constant_scale(value: float) -> ScaleRange:
    return ScaleRange(start=value, end=value)


# One deterministic, fully-validated MotionPlan per preset, built once at
# import time. Each preset's scale stays >= 1.0 throughout (see
# schemas.py's MIN_SCALE note) so a pan/rotate never reveals the source
# frame's edges.
_PRESET_DEFAULTS: dict[MotionPresetName, MotionPlan] = {
    MotionPresetName.STATIC: MotionPlan(
        preset=MotionPresetName.STATIC,
        duration=_DEFAULT_DURATION,
        scale=_constant_scale(1.0),
        position=_CENTER,
        rotation=_NO_ROTATION,
        easing=Easing.LINEAR,
    ),
    MotionPresetName.SLOW_PUSH_IN: MotionPlan(
        preset=MotionPresetName.SLOW_PUSH_IN,
        duration=_DEFAULT_DURATION,
        scale=ScaleRange(start=1.0, end=1.08),
        position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.52, y_end=0.48),
        rotation=_NO_ROTATION,
        easing=Easing.EASE_IN_OUT,
    ),
    MotionPresetName.SLOW_PULL_OUT: MotionPlan(
        preset=MotionPresetName.SLOW_PULL_OUT,
        duration=_DEFAULT_DURATION,
        scale=ScaleRange(start=1.08, end=1.0),
        position=PositionRange(x_start=0.52, y_start=0.48, x_end=0.5, y_end=0.5),
        rotation=_NO_ROTATION,
        easing=Easing.EASE_IN_OUT,
    ),
    MotionPresetName.PAN_LEFT: MotionPlan(
        preset=MotionPresetName.PAN_LEFT,
        duration=_DEFAULT_DURATION,
        scale=_constant_scale(1.15),
        position=PositionRange(x_start=0.6, y_start=0.5, x_end=0.4, y_end=0.5),
        rotation=_NO_ROTATION,
        easing=Easing.EASE_IN_OUT,
    ),
    MotionPresetName.PAN_RIGHT: MotionPlan(
        preset=MotionPresetName.PAN_RIGHT,
        duration=_DEFAULT_DURATION,
        scale=_constant_scale(1.15),
        position=PositionRange(x_start=0.4, y_start=0.5, x_end=0.6, y_end=0.5),
        rotation=_NO_ROTATION,
        easing=Easing.EASE_IN_OUT,
    ),
    MotionPresetName.PAN_UP: MotionPlan(
        preset=MotionPresetName.PAN_UP,
        duration=_DEFAULT_DURATION,
        scale=_constant_scale(1.15),
        position=PositionRange(x_start=0.5, y_start=0.6, x_end=0.5, y_end=0.4),
        rotation=_NO_ROTATION,
        easing=Easing.EASE_IN_OUT,
    ),
    MotionPresetName.PAN_DOWN: MotionPlan(
        preset=MotionPresetName.PAN_DOWN,
        duration=_DEFAULT_DURATION,
        scale=_constant_scale(1.15),
        position=PositionRange(x_start=0.5, y_start=0.4, x_end=0.5, y_end=0.6),
        rotation=_NO_ROTATION,
        easing=Easing.EASE_IN_OUT,
    ),
    MotionPresetName.ZOOM_AND_PAN: MotionPlan(
        preset=MotionPresetName.ZOOM_AND_PAN,
        duration=_DEFAULT_DURATION,
        scale=ScaleRange(start=1.0, end=1.15),
        position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.6, y_end=0.4),
        rotation=_NO_ROTATION,
        easing=Easing.EASE_IN_OUT,
    ),
    MotionPresetName.SUBTLE_ROTATE: MotionPlan(
        preset=MotionPresetName.SUBTLE_ROTATE,
        duration=_DEFAULT_DURATION,
        scale=_constant_scale(1.05),
        position=_CENTER,
        rotation=RotationRange(start=-3.0, end=3.0),
        easing=Easing.EASE_IN_OUT,
    ),
}


def list_presets() -> list[MotionPresetName]:
    return list(_PRESET_DEFAULTS.keys())


def build_motion_plan(preset: MotionPresetName | str, *, duration: float | None = None) -> MotionPlan:
    """Resolve a preset name into a full MotionPlan. Deterministic: two
    calls with the same arguments always produce an equal MotionPlan.

    Raises ValueError for an unknown preset name, and pydantic's
    ValidationError if `duration` is supplied but out of range -- the
    override is re-validated through MotionPlan's own constructor rather
    than patched in unchecked, so an out-of-range override can never
    bypass the same rules a direct MotionPlan(...) call enforces.
    """
    try:
        preset_name = MotionPresetName(preset)
    except ValueError as exc:
        valid = ", ".join(p.value for p in MotionPresetName)
        raise ValueError(f"Unknown motion preset {preset!r}; must be one of: {valid}") from exc

    data = _PRESET_DEFAULTS[preset_name].model_dump()
    if duration is not None:
        data["duration"] = duration
    return MotionPlan(**data)
