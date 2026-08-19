"""The Composition domain contract: a declarative `CompositionPlan` -- an
ordered list of `Scene`s, each with enough information (duration, source
asset, motion, caption, audio/SFX, transition, output format) for a future
renderer to produce a finished video. See
docs/features/video_factory_architecture.md and
docs/features/22-composition-contract.md.

This module performs no rendering and has no dependency on ffmpeg, any AI
provider, any TTS provider, or any image generator -- it only defines what
a fully-resolved, renderable plan looks like.

Per app/modules/README.md, this module must never import
app.modules.beat, app.modules.asset, app.modules.motion, app.modules.ai,
app.modules.scene_cutter, or app.modules.video_composer. Composing a real
CompositionPlan out of a live BeatPlan + resolved Assets + MotionPlans +
captions + audio is therefore NOT this module's job -- it belongs to a
future application/service-level orchestrator that already has legitimate
access to all of those modules (see this task's feature doc for why). What
this module owns is only the *shape* of the result.

Consequently, `SceneMotion` below deliberately duplicates the numeric shape
of `app.modules.motion.schemas.MotionPlan` (scale/position/rotation/easing,
with the same value bounds) rather than importing it -- "duplicate the
pattern, don't import the module" is the established convention in this
codebase (see e.g. the tkinter folder-picker duplicated verbatim across
scene_cutter/router.py and video_composer/router.py). The two contracts are
independently owned; if Motion's bounds ever need to diverge from
Composition's, that's a deliberate choice for each to make on its own.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# -- Motion (duplicated shape, not imported -- see module docstring) --------

MIN_SCALE = 1.0
MAX_SCALE = 4.0
MIN_POSITION = 0.0
MAX_POSITION = 1.0
MAX_ROTATION_DEGREES = 30.0


class Easing(str, Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"


class ScaleRange(BaseModel):
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


class SceneMotion(BaseModel):
    """The resolved motion for one scene. `preset_name` is a free-form,
    unvalidated label (e.g. "slow_push_in") kept only for traceability/
    debugging -- it is NOT checked against Motion's own preset taxonomy,
    since that would require importing app.modules.motion. The fields that
    actually matter to a renderer (scale/position/rotation/easing) are
    validated here directly. There is no separate `duration` here -- a
    scene's motion animates across the whole of `Scene.duration`, so a
    second, potentially-disagreeing duration field would only invite drift.
    """

    model_config = ConfigDict(extra="forbid")

    preset_name: str | None = None
    scale: ScaleRange
    position: PositionRange
    rotation: RotationRange = Field(default_factory=RotationRange)
    easing: Easing = Easing.EASE_IN_OUT


# -- Caption (duplicated shape, not imported) --------------------------------


class CaptionPreset(str, Enum):
    """Mirrors `app.modules.video_composer.models.CAPTION_PRESETS` by value,
    not by import (see module docstring) -- video_composer owns the actual
    ASS rendering for each of these; this enum only lets a CompositionPlan
    declare which one it wants.
    """

    EMOTIONAL = "emotional"
    CINEMATIC = "cinematic"
    WORD_HIGHLIGHT = "word_highlight"
    BIG_STATEMENT = "big_statement"
    QUOTE = "quote"
    TOP = "top"


class SceneCaption(BaseModel):
    """On-screen caption for this scene. Mirrors the shape of
    `app.modules.beat.schemas.CaptionConfig` without importing it. `preset`
    is per-scene metadata for a future per-scene-styled renderer; the
    renderer built in this task applies one `CompositionPlan.caption_preset`
    to the whole composition (see that field's docstring for why).
    """

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    preset: CaptionPreset | None = None


# -- Audio --------------------------------------------------------------------

MIN_VOLUME = 0.0
MAX_VOLUME = 2.0


class SceneAudio(BaseModel):
    """Per-scene sound-effect cue, and (since
    docs/features/36-audio-pipeline.md) an optional per-scene local
    narration asset -- mirrors `app.modules.beat.schemas.Beat.narration_asset_id`
    without importing it (same "duplicate the pattern" convention as
    SceneMotion/SceneCaption above). Composition-wide TTS narration (see
    CompositionPlan.narration_script) is still the fallback: a renderer
    uses per-scene local narration when *any* scene has one, otherwise the
    existing single script/voice TTS contract, unchanged -- see the feature
    doc for why mixing the two per-scene is out of scope.
    """

    model_config = ConfigDict(extra="forbid")

    sfx: str | None = None
    sfx_volume: float = 1.0
    narration_asset_id: int | None = None

    @field_validator("sfx_volume")
    @classmethod
    def _sfx_volume_within_bounds(cls, value: float) -> float:
        if not (MIN_VOLUME <= value <= MAX_VOLUME):
            raise ValueError(f"sfx_volume must be between {MIN_VOLUME} and {MAX_VOLUME}, got {value}")
        return value

    @field_validator("narration_asset_id")
    @classmethod
    def _narration_asset_id_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("narration_asset_id must be a positive integer if provided")
        return value


# -- Transition ---------------------------------------------------------------

MIN_TRANSITION_DURATION = 0.0
MAX_TRANSITION_DURATION = 3.0


class TransitionType(str, Enum):
    CUT = "cut"
    CROSSFADE = "crossfade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    FADE_TO_BLACK = "fade_to_black"


class SceneTransition(BaseModel):
    """How this scene transitions in from the previous one. A `duration` of
    0 with `type=cut` is a hard cut -- the default, so a scene that doesn't
    care about transitions doesn't have to specify one.
    """

    model_config = ConfigDict(extra="forbid")

    type: TransitionType = TransitionType.CUT
    duration: float = 0.0

    @field_validator("duration")
    @classmethod
    def _within_transition_bounds(cls, value: float) -> float:
        if not (MIN_TRANSITION_DURATION <= value <= MAX_TRANSITION_DURATION):
            raise ValueError(
                f"transition duration must be between {MIN_TRANSITION_DURATION} and "
                f"{MAX_TRANSITION_DURATION} seconds, got {value}"
            )
        return value


# -- Output format --------------------------------------------------------------


class OutputFormat(BaseModel):
    """The pixel dimensions/frame rate a scene should be rendered at.
    Required per scene (not just once per plan) since a composition can, in
    principle, mix assets that need different target formats -- most
    callers will simply give every scene the same OutputFormat.
    """

    model_config = ConfigDict(extra="forbid")

    width: int
    height: int
    fps: float = 30.0

    @field_validator("width", "height")
    @classmethod
    def _dimension_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("width/height must be > 0")
        return value

    @field_validator("fps")
    @classmethod
    def _fps_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("fps must be > 0")
        return value


# -- Scene / CompositionPlan --------------------------------------------------

MIN_DURATION = 0.1
MAX_DURATION = 120.0


class Scene(BaseModel):
    """One segment of a renderable composition: enough information for a
    future renderer to produce duration, source asset, motion, caption,
    audio/SFX, transition, and output format -- nothing more. `beat_id` is a
    bare, unconstrained reference (no FK, no import of app.modules.beat) to
    the Beat this scene was built from, for traceability only.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    order: int
    beat_id: str | None = None
    duration: float
    # Bare, unconstrained reference to an app.modules.asset Asset.id -- no
    # FK, no import. Required (not Optional): a scene with no asset
    # attached is an incomplete composition, not a valid one -- see
    # `_asset_id_is_assigned` below, which is this contract's "missing
    # asset" guard.
    source_asset_id: int
    motion: SceneMotion
    caption: SceneCaption = Field(default_factory=SceneCaption)
    audio: SceneAudio = Field(default_factory=SceneAudio)
    transition: SceneTransition = Field(default_factory=SceneTransition)
    output_format: OutputFormat

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Scene.id must not be blank")
        return value

    @field_validator("order")
    @classmethod
    def _order_is_one_based(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Scene.order must be >= 1 (1-based)")
        return value

    @field_validator("duration")
    @classmethod
    def _duration_within_bounds(cls, value: float) -> float:
        if not (MIN_DURATION <= value <= MAX_DURATION):
            raise ValueError(f"Scene.duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {value}")
        return value

    @field_validator("source_asset_id")
    @classmethod
    def _asset_id_is_assigned(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Scene.source_asset_id must reference a real asset (missing asset)")
        return value


MIN_DUCKING_RATIO = 1.0
MAX_DUCKING_RATIO = 20.0
MIN_FADE_SEC = 0.0
MAX_FADE_SEC = 10.0


class CompositionPlan(BaseModel):
    """An ordered set of Scenes ready for rendering. `video_id` is a bare,
    unconstrained reference (no FK) to the Library video this composition
    was made for, if any -- same convention as
    `app.modules.beat.schemas.BeatPlan.video_id`. `narration_script`/
    `voice`/`language`/`music_*`/`narration_volume`/`music_ducking_ratio`/
    `fade_*`/`caption_preset` are all composition-wide (not per-scene)
    specifically so they map directly onto `app.modules.video_composer`'s
    existing job-level fields when this plan is handed off for rendering --
    see the feature doc's "Output" section. `music_ducking_ratio` mirrors
    ffmpeg's own `sidechaincompress` `ratio` parameter directly (1.0 = no
    ducking, 20.0 = ffmpeg's own maximum) rather than an approximate dB
    value, so this number means exactly what video_composer's renderer does
    with it -- no unit-conversion guesswork at the adapter boundary.
    """

    model_config = ConfigDict(extra="forbid")

    video_id: int | None = None
    narration_script: str | None = None
    voice: str = "en-US-GuyNeural"
    language: str | None = None
    narration_volume: float = 1.0
    music_path: str | None = None
    music_volume: float = 0.15
    music_ducking_ratio: float = 8.0
    fade_in_sec: float = 0.0
    fade_out_sec: float = 0.0
    caption_preset: CaptionPreset = CaptionPreset.EMOTIONAL
    scenes: list[Scene] = Field(default_factory=list)

    @field_validator("narration_volume", "music_volume")
    @classmethod
    def _volume_within_bounds(cls, value: float) -> float:
        if not (MIN_VOLUME <= value <= MAX_VOLUME):
            raise ValueError(f"volume must be between {MIN_VOLUME} and {MAX_VOLUME}, got {value}")
        return value

    @field_validator("music_ducking_ratio")
    @classmethod
    def _ducking_ratio_within_bounds(cls, value: float) -> float:
        if not (MIN_DUCKING_RATIO <= value <= MAX_DUCKING_RATIO):
            raise ValueError(
                f"music_ducking_ratio must be between {MIN_DUCKING_RATIO} and {MAX_DUCKING_RATIO}, got {value}"
            )
        return value

    @field_validator("fade_in_sec", "fade_out_sec")
    @classmethod
    def _fade_within_bounds(cls, value: float) -> float:
        if not (MIN_FADE_SEC <= value <= MAX_FADE_SEC):
            raise ValueError(f"fade duration must be between {MIN_FADE_SEC} and {MAX_FADE_SEC} seconds, got {value}")
        return value

    @model_validator(mode="after")
    def _validate_contiguous_ordering(self) -> "CompositionPlan":
        orders = sorted(scene.order for scene in self.scenes)
        expected = list(range(1, len(self.scenes) + 1))
        if orders != expected:
            raise ValueError(
                "CompositionPlan.scenes ordering must be a contiguous 1-based "
                f"sequence with no duplicates or gaps; got {orders}, expected {expected}"
            )
        return self

    @property
    def total_duration(self) -> float:
        return sum(scene.duration for scene in self.scenes)

    def ordered_scenes(self) -> list[Scene]:
        return sorted(self.scenes, key=lambda scene: scene.order)
