"""The Beat domain contract: a declarative description of one segment of a
video (ordering, duration, narration, visual/motion/caption/audio
requirements) -- never the video itself, and never responsible for
rendering it. See docs/features/video_factory_architecture.md.

This module intentionally has no models.py/SQLAlchemy table: a Beat isn't
persisted state that changes over time via business rules, it's a
serializable plan produced once and handed to whichever future module
(asset/motion/video_composer) renders it. Pydantic already gives everything
a "framework-independent contract" needs -- validation, serialization,
deserialization -- without any FastAPI or SQLAlchemy dependency, so these
BaseModels are the domain model, not a second copy of one. The filesystem
artifact (beats.json, see service.py) is the source of truth, not a table.

Per app/modules/README.md, this module must never import
app.modules.asset, app.modules.motion, app.modules.video_composer, or
app.modules.ai -- visual_query/asset_id/motion.preset/caption.preset below
are plain strings/ints, not references into those modules' schemas.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BeatType(str, Enum):
    """The role a beat plays in a short-form video's structure."""

    HOOK = "hook"
    BODY = "body"
    CTA = "cta"
    OUTRO = "outro"


class VisualRequirement(BaseModel):
    """What this beat needs on screen. `asset_id` is a bare, unconstrained
    reference (no FK -- this module never imports app.modules.asset) to
    whichever Asset a future asset-matching step assigns; `asset_query` is
    the keyword hint used to find one until then.
    """

    model_config = ConfigDict(extra="forbid")

    asset_query: list[str] = Field(default_factory=list)
    asset_id: int | None = None


class MotionConfig(BaseModel):
    """Which motion preset (e.g. "slow_push_in", "pan_left") a future
    motion-rendering step should apply. `None` means static/no motion.
    The preset name is opaque here -- this module doesn't know or care what
    presets exist, that's app.modules.motion's concern.
    """

    model_config = ConfigDict(extra="forbid")

    preset: str | None = None


class CaptionConfig(BaseModel):
    """Caption text/style for this beat. `text` defaults to the beat's own
    narration when unset (a caption doesn't have to repeat narration
    verbatim -- e.g. a shortened on-screen version).
    """

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    preset: str | None = None


class AudioConfig(BaseModel):
    """Optional sound-effect cue for this beat. `sfx` is an opaque
    name/path a future audio-mixing step resolves -- not validated here.
    """

    model_config = ConfigDict(extra="forbid")

    sfx: str | None = None


class Beat(BaseModel):
    """One segment of a video: declarative, not renderable. See module
    docstring for why this is a plain Pydantic model with no ORM backing.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    order: int
    duration: float
    type: BeatType
    narration: str = ""
    visual: VisualRequirement = Field(default_factory=VisualRequirement)
    motion: MotionConfig = Field(default_factory=MotionConfig)
    caption: CaptionConfig = Field(default_factory=CaptionConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Beat.id must not be blank")
        return value

    @field_validator("order")
    @classmethod
    def _order_is_one_based(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Beat.order must be >= 1 (1-based)")
        return value

    @field_validator("duration")
    @classmethod
    def _duration_is_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Beat.duration must be > 0 seconds")
        return value


class BeatPlan(BaseModel):
    """An ordered set of Beats derived from one script. `video_id` is a
    bare, unconstrained reference (no FK -- see module docstring) to the
    Library video this plan was made for, if any; a plan can equally be made
    from a script that was never attached to a video.
    """

    model_config = ConfigDict(extra="forbid")

    video_id: int | None = None
    script_text: str | None = None
    beats: list[Beat] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_contiguous_ordering(self) -> "BeatPlan":
        orders = sorted(beat.order for beat in self.beats)
        expected = list(range(1, len(self.beats) + 1))
        if orders != expected:
            raise ValueError(
                "BeatPlan.beats ordering must be a contiguous 1-based "
                f"sequence with no duplicates or gaps; got {orders}, expected {expected}"
            )
        return self

    @property
    def total_duration(self) -> float:
        return sum(beat.duration for beat in self.beats)

    def ordered_beats(self) -> list[Beat]:
        return sorted(self.beats, key=lambda beat: beat.order)
