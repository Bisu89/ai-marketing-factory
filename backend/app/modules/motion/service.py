"""Motion planning: resolves a named preset (e.g. "slow_push_in") into a
fully-parameterized MotionPlan. Pure and deterministic -- the same preset
(and duration/intensity/focal-point/override, if given) always produces an
equal plan, with no randomness, no I/O, and no external state.

Deliberately contains no ffmpeg/subprocess/rendering code of any kind, and
no filesystem or database access -- this module only plans motion, per the
task's "does NOT render video" boundary. A future rendering layer consumes
the MotionPlan this produces; it is not part of this module and this
module must never import it.

Task 23 (see docs/features/49-local-motion-engine.md) adds two axes on top
of the original 9 fixed presets, both purely as *inputs* to the same
deterministic formula, never a second preset table:

- **Intensity** (SUBTLE/MEDIUM/STRONG) scales every preset's own
  scale/position/rotation delta from its own MEDIUM baseline -- MEDIUM is
  numerically identical to every preset's original, already-tuned values
  (see _PRESET_TEMPLATES below), so intensity=MEDIUM (the default) changes
  nothing about a pre-Task-23 render.
- **Focal point** (focal_x/focal_y, default 0.5/0.5 = frame center) shifts
  the *pivot* every preset pans/zooms around, without changing the shape of
  the motion itself. A preset's own template stores its position purely as
  an offset from this pivot, not an absolute frame coordinate, so a preset
  keeps its own character (e.g. "pan across the frame") anywhere the focal
  point happens to be, rather than needing 9 separate focal-aware variants.
"""

from dataclasses import dataclass

from app.modules.motion.schemas import (
    INTENSITY_MULTIPLIERS,
    MAX_POSITION,
    MAX_SCALE,
    MIN_POSITION,
    MIN_SCALE,
    Easing,
    MotionIntensity,
    MotionPlan,
    MotionPresetName,
    PositionRange,
    RotationRange,
    ScaleRange,
)

# Default duration for every preset. A specific beat's actual on-screen
# time is Beat's concern (see app/modules/beat/schemas.py's Beat.duration),
# not Motion's -- this is only the fallback used when a caller doesn't ask
# for a different duration via build_motion_plan(duration=...). 4 seconds
# also matches the task brief's own slow_push_in example.
_DEFAULT_DURATION = 4.0

_DEFAULT_FOCAL = 0.5


@dataclass(frozen=True)
class _PresetTemplate:
    """One preset's motion *shape*, expressed relative to its own pivot
    (the focal point) and its own MEDIUM-intensity delta -- never an
    absolute frame position or a hardcoded final number. build_motion_plan
    is what turns this into a real, clamped MotionPlan.
    """

    scale_start_delta: float
    scale_end_delta: float
    pos_start_dx: float
    pos_start_dy: float
    pos_end_dx: float
    pos_end_dy: float
    rotation_start_delta: float = 0.0
    rotation_end_delta: float = 0.0
    easing: Easing = Easing.EASE_IN_OUT


# Every delta below is exactly what reproduces this module's own original
# (pre-Task-23) hardcoded preset numbers at MotionIntensity.MEDIUM and a
# focal point of frame-center (0.5, 0.5) -- see docs/features/49-local-
# motion-engine.md for the worked-out derivation. Nothing about an existing
# project's rendered output changes unless it opts into a different
# intensity or a real focal point.
_PRESET_TEMPLATES: dict[MotionPresetName, _PresetTemplate] = {
    MotionPresetName.STATIC: _PresetTemplate(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, easing=Easing.LINEAR),
    MotionPresetName.SLOW_PUSH_IN: _PresetTemplate(0.0, 0.08, 0.0, 0.0, 0.02, -0.02),
    MotionPresetName.SLOW_PULL_OUT: _PresetTemplate(0.08, 0.0, 0.02, -0.02, 0.0, 0.0),
    MotionPresetName.PAN_LEFT: _PresetTemplate(0.15, 0.15, 0.1, 0.0, -0.1, 0.0),
    MotionPresetName.PAN_RIGHT: _PresetTemplate(0.15, 0.15, -0.1, 0.0, 0.1, 0.0),
    MotionPresetName.PAN_UP: _PresetTemplate(0.15, 0.15, 0.0, 0.1, 0.0, -0.1),
    MotionPresetName.PAN_DOWN: _PresetTemplate(0.15, 0.15, 0.0, -0.1, 0.0, 0.1),
    MotionPresetName.ZOOM_AND_PAN: _PresetTemplate(0.0, 0.15, 0.0, 0.0, 0.1, -0.1),
    MotionPresetName.SUBTLE_ROTATE: _PresetTemplate(0.05, 0.05, 0.0, 0.0, 0.0, 0.0, -3.0, 3.0),
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def list_presets() -> list[MotionPresetName]:
    return list(_PRESET_TEMPLATES.keys())


def build_motion_plan(
    preset: MotionPresetName | str,
    *,
    duration: float | None = None,
    intensity: MotionIntensity | str = MotionIntensity.MEDIUM,
    focal_x: float = _DEFAULT_FOCAL,
    focal_y: float = _DEFAULT_FOCAL,
) -> MotionPlan:
    """Resolve a preset name (+ intensity + focal point) into a full
    MotionPlan. Deterministic: the same arguments always produce an equal
    MotionPlan.

    Raises ValueError for an unknown preset/intensity name, and pydantic's
    ValidationError if `duration` (or a clamped scale/position, in the
    unexpected event clamping still lands out of bounds) is out of range --
    every value is re-validated through MotionPlan's own constructor rather
    than patched in unchecked.
    """
    try:
        preset_name = MotionPresetName(preset)
    except ValueError as exc:
        valid = ", ".join(p.value for p in MotionPresetName)
        raise ValueError(f"Unknown motion preset {preset!r}; must be one of: {valid}") from exc
    try:
        intensity_level = MotionIntensity(intensity)
    except ValueError as exc:
        valid = ", ".join(i.value for i in MotionIntensity)
        raise ValueError(f"Unknown motion intensity {intensity!r}; must be one of: {valid}") from exc

    template = _PRESET_TEMPLATES[preset_name]
    multiplier = INTENSITY_MULTIPLIERS[intensity_level]

    scale_start = _clamp(1.0 + template.scale_start_delta * multiplier, MIN_SCALE, MAX_SCALE)
    scale_end = _clamp(1.0 + template.scale_end_delta * multiplier, MIN_SCALE, MAX_SCALE)

    x_start = _clamp(focal_x + template.pos_start_dx * multiplier, MIN_POSITION, MAX_POSITION)
    y_start = _clamp(focal_y + template.pos_start_dy * multiplier, MIN_POSITION, MAX_POSITION)
    x_end = _clamp(focal_x + template.pos_end_dx * multiplier, MIN_POSITION, MAX_POSITION)
    y_end = _clamp(focal_y + template.pos_end_dy * multiplier, MIN_POSITION, MAX_POSITION)

    rotation_start = template.rotation_start_delta * multiplier
    rotation_end = template.rotation_end_delta * multiplier

    return MotionPlan(
        preset=preset_name,
        duration=_DEFAULT_DURATION if duration is None else duration,
        scale=ScaleRange(start=scale_start, end=scale_end),
        position=PositionRange(x_start=x_start, y_start=y_start, x_end=x_end, y_end=y_end),
        rotation=RotationRange(start=rotation_start, end=rotation_end),
        easing=template.easing,
    )


# -- Deterministic auto-selection (Task 23 sections 8/9/28/29) -------------
#
# No AI call, ever -- a plain keyword table (visual intent) and a fixed
# rotation (beat index) are the only two inputs. Keyword rules take
# priority over the rotation (a real content signal beats an arbitrary
# index), and the rotation itself never depends on randomness -- the same
# (beat_index, visual_hint) always selects the same preset, on every run
# and every retry.

# section 9's own example table -- checked as substring keywords against a
# lowercased visual_hint, first match wins. Deliberately small and
# reviewable, not a learned/ML classifier.
_INTENT_RULES: list[tuple[tuple[str, ...], MotionPresetName]] = [
    (("emotional", "intimate", "portrait", "close-up", "closeup"), MotionPresetName.SLOW_PUSH_IN),
    (("wide", "establishing", "landscape", "skyline"), MotionPresetName.SLOW_PULL_OUT),
    (("explanation", "documentary", "tutorial", "how-to", "how to"), MotionPresetName.PAN_RIGHT),
    (("static", "information", "chart", "graph", "text", "quote"), MotionPresetName.STATIC),
]

# The rotation pool a beat with no visual-intent match cycles through by
# its own 1-based order (section 29's own worked example: 01 zoom in, 02
# pan right, 03 zoom out, 04 pan left, ...) -- every entry is a real,
# already-implemented preset, never STATIC by itself (a rotation whose
# only member was "no motion" wouldn't be a rotation).
_ROTATION_POOL: tuple[MotionPresetName, ...] = (
    MotionPresetName.SLOW_PUSH_IN,
    MotionPresetName.PAN_RIGHT,
    MotionPresetName.SLOW_PULL_OUT,
    MotionPresetName.PAN_LEFT,
    MotionPresetName.ZOOM_AND_PAN,
    MotionPresetName.PAN_UP,
    MotionPresetName.PAN_DOWN,
)


def select_auto_motion(beat_order: int, visual_hint: str | None) -> MotionPresetName:
    """Deterministic motion selection for a beat with no manual
    `motion_preset` override, used only when a project opts into
    `MotionProjectConfig.auto_rotate` (see beat/schemas.py) -- the
    alternative to every unset beat silently reusing the exact same
    `default_preset` (section 29's own explicit complaint).
    """
    hint = (visual_hint or "").lower()
    for keywords, preset in _INTENT_RULES:
        if any(keyword in hint for keyword in keywords):
            return preset
    return _ROTATION_POOL[(max(beat_order, 1) - 1) % len(_ROTATION_POOL)]
