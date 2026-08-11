"""The Motion domain contract: a deterministic, declarative description of
how a still image or video scene should move on screen (a Ken-Burns-style
push/pull/pan/rotate) -- never the rendering of that motion. See
docs/features/video_factory_architecture.md and
docs/features/19-beat-domain-contract.md, whose "Pydantic models are the
domain model" decision this module follows for the same reason: there is
no persisted state and no FastAPI/SQLAlchemy dependency needed here, so a
second, framework-independent dataclass layer mirroring these BaseModels
field-for-field would only duplicate them.

Nothing in this file (or service.py) imports ffmpeg, subprocess, or any
rendering library -- see service.py's docstring. A MotionPlan is a
renderable *instruction*, produced once, for a future rendering layer to
consume; this module only defines what that instruction looks like and how
to build one deterministically from a named preset.

Field names use `start`/`end` rather than the task brief's illustrative
`from`/`to` -- `from` is a reserved Python keyword, and start/end carries
the same meaning without alias plumbing.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Easing(str, Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"


class MotionPresetName(str, Enum):
    STATIC = "static"
    SLOW_PUSH_IN = "slow_push_in"
    SLOW_PULL_OUT = "slow_pull_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    PAN_UP = "pan_up"
    PAN_DOWN = "pan_down"
    ZOOM_AND_PAN = "zoom_and_pan"
    SUBTLE_ROTATE = "subtle_rotate"


# A Ken-Burns-style effect needs headroom to pan/rotate within the source
# frame without ever revealing its edges, so scale can never go below 1.0
# (the untouched source size). The upper bound is just a sanity cap against
# a nonsensical, near-unusable close-up.
MIN_SCALE = 1.0
MAX_SCALE = 4.0

# Position is a fractional focus point within the frame (0.0..1.0 on each
# axis, 0.5/0.5 = dead center) -- the same convention ffmpeg's zoompan
# filter (a future rendering layer, not this module) uses for its x/y
# expressions.
MIN_POSITION = 0.0
MAX_POSITION = 1.0

# "subtle_rotate" is subtle by construction: this bound is what keeps any
# preset's rotation from drifting into a disorienting spin.
MAX_ROTATION_DEGREES = 30.0

MIN_DURATION = 0.1
MAX_DURATION = 120.0


class ScaleRange(BaseModel):
    """Zoom level over the motion's duration, as a multiple of the source's
    native size (1.0 = no zoom)."""

    model_config = ConfigDict(extra="forbid")

    start: float
    end: float

    @field_validator("start", "end")
    @classmethod
    def _within_scale_bounds(cls, value: float) -> float:
        if not (MIN_SCALE <= value <= MAX_SCALE):
            raise ValueError(f"scale must be between {MIN_SCALE} and {MAX_SCALE}, got {value}")
        return value


class PositionRange(BaseModel):
    """Focus point over the motion's duration, as a fraction of the frame
    on each axis (0.0..1.0)."""

    model_config = ConfigDict(extra="forbid")

    x_start: float
    y_start: float
    x_end: float
    y_end: float

    @field_validator("x_start", "y_start", "x_end", "y_end")
    @classmethod
    def _within_frame(cls, value: float) -> float:
        if not (MIN_POSITION <= value <= MAX_POSITION):
            raise ValueError(f"position must be between {MIN_POSITION} and {MAX_POSITION}, got {value}")
        return value


class RotationRange(BaseModel):
    """Rotation in degrees over the motion's duration. Defaults to no
    rotation -- only `subtle_rotate` uses a non-zero range."""

    model_config = ConfigDict(extra="forbid")

    start: float = 0.0
    end: float = 0.0

    @field_validator("start", "end")
    @classmethod
    def _within_rotation_bounds(cls, value: float) -> float:
        if not (-MAX_ROTATION_DEGREES <= value <= MAX_ROTATION_DEGREES):
            raise ValueError(
                f"rotation must be between -{MAX_ROTATION_DEGREES} and {MAX_ROTATION_DEGREES} "
                f"degrees, got {value}"
            )
        return value


class MotionPlan(BaseModel):
    """A fully-parameterized, renderable motion instruction for one still
    image or video scene. Purely declarative -- nothing here renders
    anything; a future rendering layer (not part of this module, and this
    module must never import it) turns this into an actual ffmpeg filter.
    """

    model_config = ConfigDict(extra="forbid")

    preset: MotionPresetName
    duration: float
    scale: ScaleRange
    position: PositionRange
    rotation: RotationRange = Field(default_factory=RotationRange)
    easing: Easing = Easing.EASE_IN_OUT

    @field_validator("duration")
    @classmethod
    def _duration_within_bounds(cls, value: float) -> float:
        if not (MIN_DURATION <= value <= MAX_DURATION):
            raise ValueError(f"duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {value}")
        return value
