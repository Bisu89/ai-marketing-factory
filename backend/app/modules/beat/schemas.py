"""The Beat domain contract: a declarative description of one segment of a
video (ordering, duration, narration, a plain-text hint of what should be on
screen) -- never the video itself, and never responsible for rendering it.
See docs/features/video_factory_architecture.md.

A Beat does not know about FFmpeg and does not call an AI provider --
rendering is a later pipeline step that consumes a Beat, not a field on
Beat itself. `asset_id`, `motion_preset`, and `narration_asset_id` are the
exceptions: bare, unconstrained references a Beat carries but never
resolves itself. `asset_id` (no FK, no import of app.modules.asset) is
whichever local image a Visual-selection step picked. `motion_preset` is a
semantic label only -- "SLOW_PUSH_IN", not a zoom curve or FFmpeg filter
graph. `narration_asset_id` (same no-FK convention as `asset_id`) is an
optional local pre-recorded audio file for this beat's narration --
resolving any of these three into real render parameters/files is entirely
a future rendering step's job, never Beat's own.

`motion_preset` is intentionally its own small enum here, not an import of
app.modules.motion.schemas.MotionPresetName (that module already exists,
with 9 lowercase presets used by the composition/rendering side of this
pipeline -- see docs/features/21-motion-domain-presets.md). Importing it
would violate this module's isolation rule below; duplicating just the 6
presets this task calls for, in Beat's own uppercase style (matching
`type` above), is the same deliberate boundary-duplication this codebase
already uses everywhere a Python value needs to be understood on both
sides of a module boundary it can't import across.

This module intentionally has no models.py/SQLAlchemy table: a Beat isn't
persisted state that changes over time via business rules, it's a
serializable plan. Pydantic already gives everything a "framework-independent
contract" needs -- validation, serialization, deserialization -- without any
FastAPI or SQLAlchemy dependency, so these BaseModels are the domain model,
not a second copy of one. The filesystem artifact (beats.json, see
service.py) is the source of truth, not a table.

Per app/modules/README.md, this module must never import
app.modules.asset, app.modules.motion, app.modules.video_composer, or
app.modules.ai.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.core.render_profile import DEFAULT_RENDER_PROFILE_NAME, RENDER_PROFILES

MIN_DURATION = 0.1
# Matches app.modules.motion.schemas.MAX_DURATION / app.modules.composition
# .schemas.MAX_DURATION -- the same upper bound already established for one
# renderable segment elsewhere in this pipeline, reused here rather than
# inventing a new, disagreeing limit.
MAX_DURATION = 120.0


class BeatType(str, Enum):
    """The role a beat plays in a short-form video's structure."""

    HOOK = "HOOK"
    SETUP = "SETUP"
    BUILD = "BUILD"
    REVEAL = "REVEAL"
    REACTION = "REACTION"
    ENDING = "ENDING"
    BODY = "BODY"


class BeatMotionPreset(str, Enum):
    """A deterministic, local camera-movement preset. Not
    app.modules.motion.schemas.MotionPresetName; see module docstring for
    why these are deliberately separate, same-spirit enums (spelling
    matches exactly, just case, so `.value.lower()` always resolves to a
    real MotionPresetName -- see batch_render.py's beat_to_scene).

    Task 23 (see docs/features/49-local-motion-engine.md section 6/58)
    added PAN_UP/PAN_DOWN, matching motion.schemas.MotionPresetName's own
    set (minus SUBTLE_ROTATE, out of this task's explicit minimum-8 list).
    """

    STATIC = "STATIC"
    SLOW_PUSH_IN = "SLOW_PUSH_IN"
    SLOW_PULL_OUT = "SLOW_PULL_OUT"
    PAN_LEFT = "PAN_LEFT"
    PAN_RIGHT = "PAN_RIGHT"
    PAN_UP = "PAN_UP"
    PAN_DOWN = "PAN_DOWN"
    ZOOM_AND_PAN = "ZOOM_AND_PAN"


def _reject_blank_if_provided(value: str | None) -> str | None:
    if value is not None and not value.strip():
        raise ValueError("must not be blank/whitespace-only if provided")
    return value


class Beat(BaseModel):
    """One segment of a video: declarative, not renderable. See module
    docstring for why this is a plain Pydantic model with no ORM backing.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    order: int
    type: BeatType
    narration: str | None = None
    duration: float
    visual_hint: str | None = None
    # A bare app.modules.asset.models.Asset.id -- see module docstring for
    # why this is the one field on Beat that reaches toward another module,
    # and only as an opaque int, never a real FK/import.
    asset_id: int | None = None
    # None means "not explicitly set -- inherit ProjectConfig.motion.default_preset"
    # (Task 12, see effective_motion_preset() below and
    # docs/features/39-project-templates.md); a real enum value means the
    # user (or an explicit STATIC choice) overrode that default for this
    # one beat. Backward compatible: an old beats.json with an explicit
    # "motion_preset": "STATIC" (or any other value) still means exactly
    # what it always meant -- only a beat that never had the key at all
    # (or had it explicitly set to null) resolves through the project
    # default now, which for a pre-Task-12 project is STATIC anyway (see
    # DEFAULT_PROJECT_CONFIG), so no existing beat's rendered look changes.
    motion_preset: BeatMotionPreset | None = None
    # A bare app.modules.asset.models.Asset.id (type="audio") -- a local,
    # pre-recorded narration clip for this beat. None means "no local
    # narration for this beat" (silence in local-narration mode, or this
    # beat's `narration` text spoken via the existing TTS path when no beat
    # in the plan has one set at all -- see docs/features/36-audio-pipeline.md).
    # Task 22 (see docs/features/48-voice-factory-local-tts.md): the Voice
    # Factory stage also writes this field, one real per-beat narration
    # segment cut from the project's own narration.wav -- from the render
    # pipeline's own point of view this is indistinguishable from a
    # manually-uploaded local narration clip, which is exactly the point
    # (zero changes needed to app.modules.video_composer's existing
    # narration_mode="local" path).
    narration_asset_id: int | None = None
    # Task 22 -- absolute position within the project's own narration
    # timeline, in seconds (section 21/22: floating-point, never rounded
    # internally). None for every beat that hasn't gone through the Voice
    # stage yet (a freshly Beat-generated plan, or one edited by hand) --
    # `duration` alone (already required, see above) is still enough to
    # render such a beat; start/end are additive precision Voice provides
    # once real narration timing exists, never a second, disagreeing
    # duration field (section 21's own "do not duplicate timing fields").
    start: float | None = None
    end: float | None = None
    # Story-to-Scene Analysis (see docs/features/103-story-to-scene-analysis.md):
    # a real, showable image description ("what should appear on screen"),
    # distinct from visual_hint's short 3-10 word label above -- this is
    # what imagegen_generate.py's _image_prompt() now prefers as the base
    # of the AI image prompt when present, falling back to visual_hint for
    # any older/manually-authored beat that never had it set. All six of
    # these plus visual_description are optional and additive -- a beat
    # generated before this feature (or authored by hand) simply has all
    # of them None, and every downstream consumer already treats that the
    # same as "not specified."
    visual_description: str | None = None
    location: str | None = None
    time_of_day: str | None = None
    emotion: str | None = None
    camera: str | None = None
    lighting: str | None = None
    continuity_notes: str | None = None

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
    def _duration_within_bounds(cls, value: float) -> float:
        if not (MIN_DURATION <= value <= MAX_DURATION):
            raise ValueError(f"Beat.duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {value}")
        return value

    @field_validator(
        "narration", "visual_hint", "visual_description", "location",
        "time_of_day", "emotion", "camera", "lighting", "continuity_notes",
    )
    @classmethod
    def _optional_text_not_blank(cls, value: str | None) -> str | None:
        return _reject_blank_if_provided(value)

    @field_validator("asset_id", "narration_asset_id")
    @classmethod
    def _asset_id_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("asset id fields must be a positive integer if provided")
        return value

    @model_validator(mode="after")
    def _timing_window_valid(self) -> "Beat":
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError(f"Beat.end ({self.end}) must be greater than Beat.start ({self.start})")
        return self



# -- Project configuration + templates (Task 12) -----------------------------
#
# See docs/features/39-project-templates.md. A Template is pure
# configuration -- render profile, motion default, caption style, audio
# defaults -- never a second pipeline, never asset/beat/job IDs. Creating a
# project from a template just snapshots this config onto BeatPlan.config
# (below); after that, the project's own copy is authoritative and the
# template it came from can change (or a custom one be deleted) without
# affecting it. `app.core.render_profile` is imported directly (not
# duplicated) since it's app.core, not another app.modules/* package --
# the one dependency every module is already allowed to have.

# Mirrors app.modules.video_composer.models.CAPTION_PRESETS by value, not
# by import (same "duplicate the pattern" convention
# app.modules.composition.schemas.CaptionPreset already uses for the exact
# same set) -- video_composer owns the real ASS rendering for each of
# these; this module only needs to know the set of valid names.
CAPTION_PRESETS = ("emotional", "cinematic", "word_highlight", "big_statement", "quote", "top")

MIN_VOLUME = 0.0
MAX_VOLUME = 2.0


class RenderProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: str = DEFAULT_RENDER_PROFILE_NAME

    @field_validator("profile")
    @classmethod
    def _known_profile(cls, value: str) -> str:
        if value not in RENDER_PROFILES:
            raise ValueError(f"Unknown render profile {value!r}. Available profiles: {sorted(RENDER_PROFILES)}")
        return value


# Task 23 (see docs/features/49-local-motion-engine.md sections 26/15) --
# duplicated as plain string tuples rather than imported from
# app.modules.motion.schemas.MotionIntensity/motion.renderer.SHORT_SOURCE_POLICIES
# (module isolation, see module docstring -- same "duplicate a few values
# across a module boundary" convention CAPTION_PRESETS above already uses).
MOTION_INTENSITIES = ("SUBTLE", "MEDIUM", "STRONG")
SHORT_VIDEO_POLICIES = ("LOOP", "FREEZE", "REJECT")


class MotionProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # STATIC, not one of the "cinematic" presets, is the system default --
    # a template is what opts a project into motion by default (see
    # BUILTIN_TEMPLATES below); this bare ProjectConfig() default must
    # match Beat.motion_preset's own pre-Task-12 behavior exactly (see that
    # field's docstring) so an old, template-less project's resolved
    # motion never changes.
    default_preset: BeatMotionPreset = BeatMotionPreset.STATIC
    # Task 23 section 29/59 -- when True, a beat with neither a manual
    # `motion_preset` override nor a visual-intent keyword match cycles
    # through a small deterministic rotation instead of every unset beat
    # reusing this same `default_preset` (section 29's own explicit
    # complaint about "every beat = zoom in"). False by default so no
    # existing project's resolved motion changes.
    auto_rotate: bool = False
    intensity: str = "MEDIUM"
    # Section 15 -- what a video-type Beat visual asset shorter than its
    # Beat's own duration does; FREEZE (hold the last frame) is the
    # least-surprising default (never silently shortens or rejects a beat
    # a human already assigned a real, if short, video to).
    short_video_policy: str = "FREEZE"

    @field_validator("intensity")
    @classmethod
    def _known_intensity(cls, value: str) -> str:
        if value not in MOTION_INTENSITIES:
            raise ValueError(f"Unknown motion intensity {value!r}, must be one of {MOTION_INTENSITIES}")
        return value

    @field_validator("short_video_policy")
    @classmethod
    def _known_short_video_policy(cls, value: str) -> str:
        if value not in SHORT_VIDEO_POLICIES:
            raise ValueError(f"Unknown short_video_policy {value!r}, must be one of {SHORT_VIDEO_POLICIES}")
        return value


# Task 25 (see docs/features/51-caption-engine.md sections 7/8/9/10/29) --
# a reasonable, documented default per knob, not one arbitrary global
# constant with no way to tune it per project/template.
DEFAULT_CAPTION_MAX_WORDS = 7
DEFAULT_CAPTION_MAX_CHARS = 42
DEFAULT_CAPTION_MIN_DURATION_SEC = 0.8
DEFAULT_CAPTION_MAX_DURATION_SEC = 3.5
DEFAULT_CAPTION_MAX_LINES = 2
# Words a viewer can comfortably *read* per second -- a distinct concern
# from ContentProjectConfig/Settings.content_words_per_second (how fast
# the script is *spoken*, Task 21); reading a short on-screen caption
# tolerates a faster pace than natural speech does.
DEFAULT_CAPTION_READING_SPEED_WPS = 3.3

MIN_CAPTION_MAX_WORDS = 1
MAX_CAPTION_MAX_WORDS = 20
MIN_CAPTION_MAX_CHARS = 10
MAX_CAPTION_MAX_CHARS = 120
MIN_CAPTION_MAX_LINES = 1
MAX_CAPTION_MAX_LINES = 3


class CaptionsProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    preset: str = "emotional"
    max_words: int = DEFAULT_CAPTION_MAX_WORDS
    max_chars: int = DEFAULT_CAPTION_MAX_CHARS
    min_duration_sec: float = DEFAULT_CAPTION_MIN_DURATION_SEC
    max_duration_sec: float = DEFAULT_CAPTION_MAX_DURATION_SEC
    max_lines: int = DEFAULT_CAPTION_MAX_LINES
    reading_speed_wps: float = DEFAULT_CAPTION_READING_SPEED_WPS

    @field_validator("preset")
    @classmethod
    def _known_preset(cls, value: str) -> str:
        if value not in CAPTION_PRESETS:
            raise ValueError(f"Unknown caption preset {value!r}, must be one of {CAPTION_PRESETS}")
        return value

    @field_validator("max_words")
    @classmethod
    def _max_words_within_bounds(cls, value: int) -> int:
        if not (MIN_CAPTION_MAX_WORDS <= value <= MAX_CAPTION_MAX_WORDS):
            raise ValueError(f"max_words must be between {MIN_CAPTION_MAX_WORDS} and {MAX_CAPTION_MAX_WORDS}, got {value}")
        return value

    @field_validator("max_chars")
    @classmethod
    def _max_chars_within_bounds(cls, value: int) -> int:
        if not (MIN_CAPTION_MAX_CHARS <= value <= MAX_CAPTION_MAX_CHARS):
            raise ValueError(f"max_chars must be between {MIN_CAPTION_MAX_CHARS} and {MAX_CAPTION_MAX_CHARS}, got {value}")
        return value

    @field_validator("max_lines")
    @classmethod
    def _max_lines_within_bounds(cls, value: int) -> int:
        if not (MIN_CAPTION_MAX_LINES <= value <= MAX_CAPTION_MAX_LINES):
            raise ValueError(f"max_lines must be between {MIN_CAPTION_MAX_LINES} and {MAX_CAPTION_MAX_LINES}, got {value}")
        return value

    @field_validator("min_duration_sec", "max_duration_sec")
    @classmethod
    def _duration_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError(f"duration must be > 0, got {value}")
        return value

    @field_validator("reading_speed_wps")
    @classmethod
    def _reading_speed_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError(f"reading_speed_wps must be > 0, got {value}")
        return value

    @model_validator(mode="after")
    def _min_duration_not_above_max(self) -> "CaptionsProjectConfig":
        if self.min_duration_sec > self.max_duration_sec:
            raise ValueError(
                f"min_duration_sec ({self.min_duration_sec}) must not be greater than "
                f"max_duration_sec ({self.max_duration_sec})"
            )
        return self


BGM_MODES = ("AUTO", "MANUAL")
BGM_MISSING_POLICIES = ("OFF", "NEEDS_REVIEW")
MIN_DUCKING_RATIO = 1.0  # ffmpeg sidechaincompress's own "no effect" floor
MAX_DUCKING_RATIO = 20.0  # ffmpeg sidechaincompress's own documented ceiling
MAX_FADE_SECONDS = 10.0  # section 12's own "do not make fades excessively long"


class AudioProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narration_enabled: bool = True
    music_enabled: bool = True
    music_volume: float = 0.15
    ducking: bool = True
    # Task 24 (see docs/features/50-audio-master.md) -- BGM selection mode.
    # Only meaningful while music_enabled=True; music_enabled=False is this
    # config's own pre-existing, complete "BGM off" switch (section 9), not
    # duplicated here as a third bgm_mode value.
    bgm_mode: str = "AUTO"
    # Only meaningful when bgm_mode="MANUAL" -- a bare Asset.id (no FK, same
    # no-FK convention as Beat.asset_id) the user explicitly chose. Manual
    # selection always overrides automatic selection (section 8) -- the
    # composition root never re-runs auto-selection while this is set.
    bgm_asset_id: int | None = None
    # The ffmpeg sidechaincompress `ratio` parameter -- how hard the BGM
    # ducks under narration (section 15/16: never let BGM dominate). Only
    # applied while `ducking=True`.
    ducking_ratio: float = 8.0
    fade_in_sec: float = 0.5
    fade_out_sec: float = 1.0
    # Section 33/34 -- what AUTO selection does when no suitable BGM asset
    # exists at all. OFF (default): proceed narration-only, never block the
    # near-$0 factory over an unavailable music library. NEEDS_REVIEW: flag
    # it for a human instead of silently shipping without music.
    bgm_missing_policy: str = "OFF"

    @field_validator("music_volume")
    @classmethod
    def _volume_within_bounds(cls, value: float) -> float:
        if not (MIN_VOLUME <= value <= MAX_VOLUME):
            raise ValueError(f"music_volume must be between {MIN_VOLUME} and {MAX_VOLUME}, got {value}")
        return value

    @field_validator("bgm_mode")
    @classmethod
    def _known_bgm_mode(cls, value: str) -> str:
        if value not in BGM_MODES:
            raise ValueError(f"Unknown bgm_mode {value!r}, must be one of {BGM_MODES}")
        return value

    @field_validator("bgm_missing_policy")
    @classmethod
    def _known_bgm_missing_policy(cls, value: str) -> str:
        if value not in BGM_MISSING_POLICIES:
            raise ValueError(f"Unknown bgm_missing_policy {value!r}, must be one of {BGM_MISSING_POLICIES}")
        return value

    @field_validator("ducking_ratio")
    @classmethod
    def _ducking_ratio_within_bounds(cls, value: float) -> float:
        if not (MIN_DUCKING_RATIO <= value <= MAX_DUCKING_RATIO):
            raise ValueError(f"ducking_ratio must be between {MIN_DUCKING_RATIO} and {MAX_DUCKING_RATIO}, got {value}")
        return value

    @field_validator("fade_in_sec", "fade_out_sec")
    @classmethod
    def _fade_within_bounds(cls, value: float) -> float:
        if not (0.0 <= value <= MAX_FADE_SECONDS):
            raise ValueError(f"fade must be between 0 and {MAX_FADE_SECONDS} seconds, got {value}")
        return value

    @field_validator("bgm_asset_id")
    @classmethod
    def _bgm_asset_id_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("bgm_asset_id must be a positive integer if provided")
        return value


# Task 26 (see docs/features/52-final-composer.md sections 18-23) -- ffmpeg's
# own `overlay` filter exposes W/H (main video)/w/h (overlay) directly, so a
# position is just a named corner, not a free-form coordinate pair (section
# 18's own "keep the MVP simple, do not build a watermark editor").
WATERMARK_POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
MIN_WATERMARK_OPACITY = 0.05
MAX_WATERMARK_OPACITY = 1.0
MIN_WATERMARK_SCALE = 0.02
MAX_WATERMARK_SCALE = 0.6
MAX_WATERMARK_MARGIN = 500


class WatermarkProjectConfig(BaseModel):
    """Section 18/19 -- an optional brand mark burned into the Final
    Composer's own output. `asset_id` (no FK, same bare-reference
    convention as AudioProjectConfig.bgm_asset_id) is deliberately the only
    way to point at a watermark image -- section 19's own "do not accept
    arbitrary frontend filesystem paths"; the composition root resolves it
    against the existing Asset Library, exactly like BGM selection already
    does.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    asset_id: int | None = None
    position: str = "bottom-right"
    # Section 21 -- configurable, never one hardcoded brand-specific value.
    opacity: float = 0.8
    # Section 18 -- the watermark's rendered width as a fraction of the
    # output video's own width (aspect-preserving); resolution-independent
    # across SOCIAL_VERTICAL/landscape/square profiles alike.
    scale: float = 0.15
    # Section 22 -- keeps the mark off the frame edge ("safe area").
    margin_x: int = 24
    margin_y: int = 24

    @field_validator("position")
    @classmethod
    def _known_position(cls, value: str) -> str:
        if value not in WATERMARK_POSITIONS:
            raise ValueError(f"Unknown watermark position {value!r}, must be one of {WATERMARK_POSITIONS}")
        return value

    @field_validator("opacity")
    @classmethod
    def _opacity_within_bounds(cls, value: float) -> float:
        if not (MIN_WATERMARK_OPACITY <= value <= MAX_WATERMARK_OPACITY):
            raise ValueError(
                f"opacity must be between {MIN_WATERMARK_OPACITY} and {MAX_WATERMARK_OPACITY}, got {value}"
            )
        return value

    @field_validator("scale")
    @classmethod
    def _scale_within_bounds(cls, value: float) -> float:
        if not (MIN_WATERMARK_SCALE <= value <= MAX_WATERMARK_SCALE):
            raise ValueError(f"scale must be between {MIN_WATERMARK_SCALE} and {MAX_WATERMARK_SCALE}, got {value}")
        return value

    @field_validator("margin_x", "margin_y")
    @classmethod
    def _margin_within_bounds(cls, value: int) -> int:
        if not (0 <= value <= MAX_WATERMARK_MARGIN):
            raise ValueError(f"margin must be between 0 and {MAX_WATERMARK_MARGIN}, got {value}")
        return value

    @field_validator("asset_id")
    @classmethod
    def _asset_id_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("asset_id must be a positive integer if provided")
        return value


MIN_OUTRO_DURATION_SEC = 5.0
MAX_OUTRO_DURATION_SEC = 7.0
# Real user report: 80 felt needlessly restrictive once the renderer
# (app/modules/outro/renderer.py's own _fit_text) properly auto-wraps AND
# shrinks font size to guarantee the block always fits the frame -- raised
# now that overflow is no longer a risk. Still bounded (not unlimited): a
# real ffmpeg filter chain has one drawtext filter per revealed character,
# and a multi-paragraph CTA stops being a "quick CTA" at some point anyway.
MAX_OUTRO_TEXT_LENGTH = 200


class OutroProjectConfig(BaseModel):
    """Real user report: the video/audio cuts off the instant narration
    ends, with no room for a closing CTA. An optional short (5-7s) trailing
    segment appended after the main composed video -- solid black
    background, `text` revealed character-by-character (never AI-derived
    from the script -- always this exact, manually-typed string), and
    background music swelling up to full volume across the whole segment
    (see app.modules.outro's own renderer). `text` blank means nothing is
    appended even if `enabled` -- this can't be a no-op-by-accident
    footgun the other way (enabled=True with real text always renders).
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    text: str = ""
    duration_sec: float = 6.0

    @field_validator("text")
    @classmethod
    def _text_within_length(cls, value: str) -> str:
        if len(value) > MAX_OUTRO_TEXT_LENGTH:
            raise ValueError(f"Outro text must be at most {MAX_OUTRO_TEXT_LENGTH} characters, got {len(value)}")
        return value

    @field_validator("duration_sec")
    @classmethod
    def _duration_within_bounds(cls, value: float) -> float:
        if not (MIN_OUTRO_DURATION_SEC <= value <= MAX_OUTRO_DURATION_SEC):
            raise ValueError(
                f"duration_sec must be between {MIN_OUTRO_DURATION_SEC} and {MAX_OUTRO_DURATION_SEC}, got {value}"
            )
        return value


# Task 27 (see docs/features/53-thumbnail-metadata-package.md section 6/28/32)
# -- reasonable, documented defaults per knob, matching the same "no
# arbitrary global constant with no way to tune it" reasoning as Task 25's
# own DEFAULT_CAPTION_* constants.
DEFAULT_THUMBNAIL_CANDIDATE_COUNT = 6
DEFAULT_MAX_HASHTAGS = 8
MIN_THUMBNAIL_CANDIDATE_COUNT = 1
MAX_THUMBNAIL_CANDIDATE_COUNT = 12
MIN_MAX_HASHTAGS = 1
MAX_MAX_HASHTAGS = 20
# Section 32 -- a plain label, never branched on for platform-specific
# publishing logic (out of this task's scope). "general" is the
# no-platform-chosen-yet default.
PLATFORM_PROFILES = ("general", "youtube_shorts", "tiktok", "instagram_reels", "facebook_reels")


class PackageProjectConfig(BaseModel):
    """Section 3/32 -- settings for the Ready-to-Post Package stage
    (Thumbnail + Metadata). `platform_profile` is carried straight through
    into metadata.json as a label only (section 32: "do not build
    platform-specific publishing logic here") -- nothing in this task
    branches on its value.
    """

    model_config = ConfigDict(extra="forbid")

    thumbnail_headline_enabled: bool = True
    thumbnail_candidate_count: int = DEFAULT_THUMBNAIL_CANDIDATE_COUNT
    max_hashtags: int = DEFAULT_MAX_HASHTAGS
    platform_profile: str = "general"
    # Real user report: the deterministic title/description (a truncated
    # core_message) felt bland, and the thumbnail always echoed the exact
    # same text as the title. Opt-in and off by default -- unlike every
    # other Package-stage artifact, this is a real, billed AI call (see
    # package_generate.py's own _generate_ai_metadata).
    ai_metadata_enabled: bool = False

    @field_validator("thumbnail_candidate_count")
    @classmethod
    def _candidate_count_within_bounds(cls, value: int) -> int:
        if not (MIN_THUMBNAIL_CANDIDATE_COUNT <= value <= MAX_THUMBNAIL_CANDIDATE_COUNT):
            raise ValueError(
                f"thumbnail_candidate_count must be between {MIN_THUMBNAIL_CANDIDATE_COUNT} and "
                f"{MAX_THUMBNAIL_CANDIDATE_COUNT}, got {value}"
            )
        return value

    @field_validator("max_hashtags")
    @classmethod
    def _max_hashtags_within_bounds(cls, value: int) -> int:
        if not (MIN_MAX_HASHTAGS <= value <= MAX_MAX_HASHTAGS):
            raise ValueError(f"max_hashtags must be between {MIN_MAX_HASHTAGS} and {MAX_MAX_HASHTAGS}, got {value}")
        return value

    @field_validator("platform_profile")
    @classmethod
    def _known_platform_profile(cls, value: str) -> str:
        if value not in PLATFORM_PROFILES:
            raise ValueError(f"Unknown platform_profile {value!r}, must be one of {PLATFORM_PROFILES}")
        return value


class FactoryProjectConfig(BaseModel):
    """One-click production policy (Task 18 -- see
    docs/features/44-one-click-factory-pipeline.md). Governs how
    FactoryPipeline auto-assigns visuals and whether it renders
    immediately once the Quality Gate passes; it does not change how the
    Quality Gate itself scores anything (app.modules.quality is untouched).
    """

    model_config = ConfigDict(extra="forbid")

    auto_assign_high_confidence: bool = True
    require_review_for_medium_confidence: bool = True
    require_review_for_low_confidence: bool = True
    render_after_quality_pass: bool = True


# ISO-ish short codes, matching section 36's own explicit examples -- never
# inferred from user location, always the configured template/batch value.
CONTENT_LANGUAGES = ("en", "es", "vi", "pt")


class ContentProjectConfig(BaseModel):
    """Task 21's "content profile" (see
    docs/features/47-content-brief-script-engine.md section 9) -- the
    lightweight, Template-driven configuration Idea->ContentBrief->Script
    generation reads instead of a second global settings system. Same
    "named sub-config hung off ProjectConfig" shape FactoryProjectConfig
    already established (section 8: "Template determines language/duration/
    tone/structure").
    """

    model_config = ConfigDict(extra="forbid")

    language: str = "en"
    tone: str = "warm and reflective"
    style: str = "storytelling"
    target_duration: float = 30.0
    audience: str = "general audience"
    cta_enabled: bool = True

    @field_validator("language")
    @classmethod
    def _known_language(cls, value: str) -> str:
        if value not in CONTENT_LANGUAGES:
            raise ValueError(f"Unknown language {value!r}, must be one of {CONTENT_LANGUAGES}")
        return value

    @field_validator("target_duration")
    @classmethod
    def _duration_within_bounds(cls, value: float) -> float:
        if not (MIN_DURATION <= value <= MAX_DURATION):
            raise ValueError(f"target_duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {value}")
        return value


# Task 22 (see docs/features/48-voice-factory-local-tts.md section 4/41) --
# "local" (this app's own new, genuinely offline pyttsx3/SAPI5 provider) is
# the default; "edge_tts" wraps the repo's pre-existing free-but-networked
# engine as an explicit, non-default opt-in. Never a third value invented
# here without a real provider behind it (app.modules.voice.providers.get_provider).
VOICE_PROVIDERS = ("local", "edge_tts")
MIN_VOICE_SPEED = 0.5
MAX_VOICE_SPEED = 2.0


class VoiceProjectConfig(BaseModel):
    """Section 6/7's own "lightweight enough to select a local voice, not a
    voice management system" -- one more named sub-config on ProjectConfig,
    same shape as ContentProjectConfig/FactoryProjectConfig above. Language
    intentionally mirrors ContentProjectConfig.language's own codes/default
    (a project's script language and its narration language are the same
    thing in practice) but is kept as its own field rather than reused
    directly, since a user may reasonably want to narrate a script in a
    different language than it was written for review purposes.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = "local"
    voice_id: str = "default"
    language: str = "en"
    speed: float = 1.0
    pitch: int = 0

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, value: str) -> str:
        if value not in VOICE_PROVIDERS:
            raise ValueError(f"Unknown voice provider {value!r}, must be one of {VOICE_PROVIDERS}")
        return value

    @field_validator("language")
    @classmethod
    def _known_language(cls, value: str) -> str:
        if value not in CONTENT_LANGUAGES:
            raise ValueError(f"Unknown language {value!r}, must be one of {CONTENT_LANGUAGES}")
        return value

    @field_validator("speed")
    @classmethod
    def _speed_within_bounds(cls, value: float) -> float:
        if not (MIN_VOICE_SPEED <= value <= MAX_VOICE_SPEED):
            raise ValueError(f"speed must be between {MIN_VOICE_SPEED} and {MAX_VOICE_SPEED}, got {value}")
        return value


VISUAL_GENERATION_MODES = ("library", "ai_generated")


class VisualGenerationProjectConfig(BaseModel):
    """Task 59 -- "Generate Full by AI": opt-in per-project switch between
    the default "library" mode (ASSIGNING_ASSETS matches an existing local
    Asset, today's only behavior) and "ai_generated" (a new GENERATING_VISUALS
    Factory stage generates a fresh OpenAI image per beat instead -- see
    app/api/v1/endpoints/imagegen_generate.py). Defaults to "library" so
    every existing/pre-Task-59 project is completely unaffected.
    """

    model_config = ConfigDict(extra="forbid")

    mode: str = "library"
    # Free-text style guidance appended to every AI-generated beat image
    # prompt for this project/template (e.g. "watercolor illustration,
    # pastel colors, no text"). Optional -- blank means no change to the
    # existing tone/style-derived prompt. Image generation is a flat
    # per-image fee (see app/modules/imagegen/image_client.py), so a
    # longer prompt here has no cost impact.
    image_style_prompt: str = ""

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in VISUAL_GENERATION_MODES:
            raise ValueError(f"Unknown visual generation mode {value!r}, must be one of {VISUAL_GENERATION_MODES}")
        return value


class ProjectConfig(BaseModel):
    """The one, unified configuration object -- render/motion/captions/audio
    -- shared by templates and projects alike (Task 12's own "do not
    duplicate render/audio/caption config across multiple unrelated files"
    instruction). A Template's `config` and a project's (BeatPlan.config)
    are both exactly this same shape; the only difference is what wraps it
    (a Template also carries id/name/version/builtin, see below).
    """

    model_config = ConfigDict(extra="forbid")

    render: RenderProjectConfig = Field(default_factory=RenderProjectConfig)
    motion: MotionProjectConfig = Field(default_factory=MotionProjectConfig)
    captions: CaptionsProjectConfig = Field(default_factory=CaptionsProjectConfig)
    audio: AudioProjectConfig = Field(default_factory=AudioProjectConfig)
    watermark: WatermarkProjectConfig = Field(default_factory=WatermarkProjectConfig)
    outro: OutroProjectConfig = Field(default_factory=OutroProjectConfig)
    package: PackageProjectConfig = Field(default_factory=PackageProjectConfig)
    factory: FactoryProjectConfig = Field(default_factory=FactoryProjectConfig)
    content: ContentProjectConfig = Field(default_factory=ContentProjectConfig)
    voice: VoiceProjectConfig = Field(default_factory=VoiceProjectConfig)
    visual_generation: VisualGenerationProjectConfig = Field(default_factory=VisualGenerationProjectConfig)
    # Provenance only, like Beat.asset_id -- which Template (and which
    # version of it) this config was snapshotted from, if any. A project
    # created without choosing a template (or a pre-Task-12 project) has
    # both as None. Never used to look anything up at render time; the
    # config fields above are always the full, self-contained truth.
    template_id: str | None = None
    template_version: int | None = None


DEFAULT_PROJECT_CONFIG = ProjectConfig()


def effective_motion_preset(beat: Beat, config: ProjectConfig) -> BeatMotionPreset:
    """Beat override > Project default > System default (Task 12 section
    11). `config.motion.default_preset` -- not a hardcoded STATIC -- IS the
    system default at this point, since it already defaults to STATIC on a
    bare/template-less ProjectConfig (see MotionProjectConfig above), so
    there's only ever two tiers to actually implement here, not three.
    """
    return beat.motion_preset if beat.motion_preset is not None else config.motion.default_preset


class Template(BaseModel):
    """A named, reusable ProjectConfig. `builtin=True` templates
    (BUILTIN_TEMPLATES below) are fixed Python constants, never persisted
    or mutated -- creating a project from one only ever copies `config`
    (see effective_motion_preset's caller / VideoFactoryPage.tsx's
    "Use Template"), so nothing a user does to their project can reach
    back and change the template itself. `builtin=False` templates are
    user-created (see docs/features/39-project-templates.md's "Save as
    Template") and persisted in templates.json (app.modules.beat.service).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str = ""
    version: int = 1
    builtin: bool = False
    config: ProjectConfig = Field(default_factory=ProjectConfig)

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Template.id must not be blank")
        return value

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Template.name must not be blank")
        return value


EMOTIONAL_STORY_TEMPLATE = Template(
    id="emotional_story",
    name="Emotional Story",
    description="Short emotional storytelling video -- bold captions, gentle push-in motion.",
    version=1,
    builtin=True,
    config=ProjectConfig(
        render=RenderProjectConfig(profile="SOCIAL_VERTICAL"),
        motion=MotionProjectConfig(default_preset=BeatMotionPreset.SLOW_PUSH_IN),
        captions=CaptionsProjectConfig(enabled=True, preset="big_statement"),
        audio=AudioProjectConfig(narration_enabled=True, music_enabled=True, music_volume=0.18, ducking=True),
        content=ContentProjectConfig(
            language="en", tone="warm and emotional", style="storytelling",
            target_duration=30.0, audience="general audience", cta_enabled=True,
        ),
        voice=VoiceProjectConfig(provider="local", voice_id="default", language="en", speed=1.0),
        template_id="emotional_story",
        template_version=1,
    ),
)

COUPLE_STORY_TEMPLATE = Template(
    id="couple_story",
    name="Couple Story",
    description="Relationship/love/reunion/proposal stories -- subtle motion, emotional captions.",
    version=1,
    builtin=True,
    config=ProjectConfig(
        render=RenderProjectConfig(profile="SOCIAL_VERTICAL"),
        motion=MotionProjectConfig(default_preset=BeatMotionPreset.SLOW_PUSH_IN),
        captions=CaptionsProjectConfig(enabled=True, preset="emotional"),
        audio=AudioProjectConfig(narration_enabled=True, music_enabled=True, music_volume=0.15, ducking=True),
        content=ContentProjectConfig(
            language="en", tone="tender and reflective", style="relationship story",
            target_duration=30.0, audience="adults interested in relationships", cta_enabled=True,
        ),
        voice=VoiceProjectConfig(provider="local", voice_id="default", language="en", speed=0.95),
        template_id="couple_story",
        template_version=1,
    ),
)

CUSTOM_TEMPLATE = Template(
    id="custom",
    name="Custom",
    description="Start from blank -- plain system defaults, no assumptions.",
    version=1,
    builtin=True,
    config=ProjectConfig(template_id="custom", template_version=1),
)

# Note: BUILTIN_TEMPLATES' own `id`s ("emotional_story"/"couple_story"/
# "custom") are reserved -- template_service.save_custom_templates below
# rejects a custom template trying to reuse one, so a built-in can never be
# shadowed or overwritten by user data.
BUILTIN_TEMPLATES: list[Template] = [EMOTIONAL_STORY_TEMPLATE, COUPLE_STORY_TEMPLATE, CUSTOM_TEMPLATE]
BUILTIN_TEMPLATE_IDS = frozenset(t.id for t in BUILTIN_TEMPLATES)


def sanitize_project_config_for_template(config: ProjectConfig) -> ProjectConfig:
    """Project -> Template (Task 12 section 23, "Save as Template"). A
    ProjectConfig never contains asset/beat/render-job IDs or output paths
    in the first place (see ProjectConfig's own docstring/fields) -- it's
    only render/motion/captions/audio settings -- so "sanitizing" is
    exactly a deep copy with template provenance cleared, not a field-by-
    field strip list that could silently miss a newly-added sensitive
    field later.
    """
    return config.model_copy(deep=True, update={"template_id": None, "template_version": None})


# -- Content (Task 21 -- see docs/features/47-content-brief-script-engine.md) --
#
# Idea -> ContentBrief -> Script, ahead of Beat generation. ContentBrief is a
# plain nested value object stored inside Project.beat_plan_json (same "one
# JSON blob, not a dozen tables" convention BeatPlan.config already uses),
# not a separate SQL table -- it has no independent lifecycle from the
# Project it belongs to and no module outside app.modules.beat ever needs to
# query it on its own.


class ContentBrief(BaseModel):
    """AI-produced (or manually edited -- section 16, "human edits always
    win") creative direction for one video, generated from a short Idea
    before Script generation. Deliberately narrower than the brief's own
    full field list (section 5's "do not blindly create every field") --
    `language`/`target_duration` are NOT part of this model since they're
    already owned by ContentProjectConfig (the Template-driven profile),
    not something the AI decides per-idea.
    """

    model_config = ConfigDict(extra="forbid")

    topic: str
    audience: str
    angle: str
    emotion: str
    hook_strategy: str
    tone: str
    pacing: str
    core_message: str
    cta: str

    @field_validator("topic", "audience", "angle", "emotion", "hook_strategy", "tone", "pacing", "core_message", "cta")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ContentBrief fields must not be blank")
        return value


class BeatPlan(BaseModel):
    """An ordered, non-empty set of Beats derived from one script. `video_id`
    is a bare, unconstrained reference (no FK -- see module docstring) to the
    Library video this plan was made for, if any.
    """

    # Beat itself stays extra="forbid" (validating real input), but BeatPlan
    # tolerates unknown keys so that a BeatPlan this class just serialized
    # (model_dump_json() includes the computed `total_duration` below) can be
    # fed straight back into model_validate_json() without the caller having
    # to strip that key out first -- total_duration isn't a settable field,
    # just a derived value that happens to be present in its own JSON output.
    model_config = ConfigDict(extra="ignore")

    video_id: int | None = None
    script_text: str | None = None
    beats: list[Beat] = Field(default_factory=list, min_length=1)
    # Task 12 (see docs/features/39-project-templates.md) -- project_name is
    # a plain display label (this app has no multi-project store; "the
    # project" is this one BeatPlan). `config` defaults to DEFAULT_PROJECT_CONFIG
    # via default_factory, so a pre-Task-12 beats.json with neither key at
    # all loads with zero migration, exactly like motion_preset above.
    project_name: str | None = None
    config: ProjectConfig = Field(default_factory=lambda: DEFAULT_PROJECT_CONFIG.model_copy(deep=True))
    # Task 21 -- the raw one-line idea a project can be created from instead
    # of a full script (section 3). None for every pre-Task-21 project/plan
    # (backward compatible, same "absent means not applicable" convention as
    # motion_preset/config above).
    idea: str | None = None
    content_brief: ContentBrief | None = None
    # True once a human has directly written/edited script_text (section 17)
    # -- FactoryPipeline's CONTENT stage (app/api/v1/endpoints/content_generate.py)
    # must never overwrite script_text while this is set, regardless of
    # whether the current text happens to pass validation.
    script_locked: bool = False
    # Task 27 (see docs/features/53-thumbnail-metadata-package.md section
    # 21/48) -- None means "no override, derive it"; once set, these always
    # win over the Metadata Engine's own generated title/description/
    # hashtags, and are never auto-cleared by a script/idea/content edit
    # (same "sticky until the user changes it" convention as
    # AudioProjectConfig.bgm_asset_id).
    manual_title: str | None = None
    manual_description: str | None = None
    manual_hashtags: list[str] | None = None

    @computed_field
    @property
    def total_duration(self) -> float:
        return sum(beat.duration for beat in self.beats)

    @model_validator(mode="after")
    def _validate_beats(self) -> "BeatPlan":
        ids = [beat.id for beat in self.beats]
        if len(ids) != len(set(ids)):
            raise ValueError(f"BeatPlan.beats contains duplicate ids: {ids}")

        orders = sorted(beat.order for beat in self.beats)
        expected = list(range(1, len(self.beats) + 1))
        if orders != expected:
            raise ValueError(
                "BeatPlan.beats ordering must be a contiguous 1-based "
                f"sequence with no duplicates or gaps; got {orders}, expected {expected}"
            )
        return self

    def ordered_beats(self) -> list[Beat]:
        return sorted(self.beats, key=lambda beat: beat.order)


# -- Projects (Task 13 -- see docs/features/40-batch-video-creation.md) ------


class ProjectOut(BaseModel):
    """A Project's content, shaped exactly like BeatPlan (script_text/beats/
    project_name/config) but WITHOUT BeatPlan's `min_length=1` invariant on
    `beats`. A freshly batch-created project legitimately has zero beats
    until "Generate Beats for Batch" runs -- that's a real, valid lifecycle
    state for a Project (not yet ready to render), even though an empty
    BeatPlan is correctly rejected as a thing you could ever save from the
    interactive single-project editor (see BeatPlan's own
    test_empty_beats_list_rejected). Keeping these as two distinct
    contracts, rather than loosening BeatPlan itself, preserves that
    already-tested invariant exactly as-is.

    `PUT /projects/{id}/beat-plan` (see router.py) still validates its
    incoming body as a real, strict BeatPlan -- by the time a human is
    saving edits through the beat editor, "at least one beat" is exactly
    as true for a Project as it already is for the singleton beats.json.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    slug: str
    video_id: int | None = None
    script_text: str | None = None
    beats: list[Beat] = Field(default_factory=list)
    project_name: str | None = None
    config: ProjectConfig = Field(default_factory=lambda: DEFAULT_PROJECT_CONFIG.model_copy(deep=True))
    render_job_id: int | None = None
    # Series (scoped-down "100-Day Series") -- see
    # app/api/v1/endpoints/series_project.py. Both None for a project not
    # attached to a Series (every project before this feature, and every
    # one a user never attaches).
    series_id: int | None = None
    episode_number: int | None = None
    # Task 21 -- see BeatPlan's own matching fields above; ProjectOut mirrors
    # them for the exact same reason it mirrors script_text/beats/config.
    idea: str | None = None
    content_brief: ContentBrief | None = None
    script_locked: bool = False
    # Task 27 -- see BeatPlan's own matching fields above.
    manual_title: str | None = None
    manual_description: str | None = None
    manual_hashtags: list[str] | None = None

    @computed_field
    @property
    def total_duration(self) -> float:
        return sum(beat.duration for beat in self.beats)


def new_project_draft(
    script_text: str | None, project_name: str, config: ProjectConfig,
    *, idea: str | None = None, script_locked: bool = False,
) -> dict:
    """The initial `Project.beat_plan_json` for a just-created project --
    valid ProjectOut shape, deliberately NOT a valid BeatPlan yet (no
    beats). "Generate Beats for Batch" (the composition-root batch
    orchestrator) is what turns this into one plan.beats.append() at a
    time, same as the interactive Beat Editor does for the singleton flow.

    Task 21: `script_text` is now optional -- a project may instead start
    from just an `idea`, with FactoryPipeline's own CONTENT stage
    (app/api/v1/endpoints/content_generate.py) producing script_text before
    Beat generation ever runs. `script_locked` defaults to True whenever a
    real script_text is supplied directly (the classic flow -- a human typed
    it, so it's already final, never touched by automatic content
    generation) and False when only an idea is given (nothing to protect
    yet -- see project_service.create_project's own caller-side default).
    """
    return {
        "script_text": script_text,
        "beats": [],
        "project_name": project_name,
        "config": config.model_dump(mode="json"),
        "idea": idea,
        "content_brief": None,
        "script_locked": script_locked,
    }
