"""The AI Scene Director domain contract (Phase 0 of the AI Storytelling
Studio plan -- see the published architecture plan, section 14).

A pure, deterministic classification of "how should this scene be shown"
-- STILL image + Ken-Burns, still + stronger motion, or a real AI-video
clip -- plus the supporting scores and a reuse hint. NO AI/LLM call, NO
FFmpeg, NO DB, NO filesystem access, exactly like
app.modules.quality.analyzer and app.modules.composition are pure
declarative contracts rather than doers.

Per app/modules/README.md, this module must never import another module.
`SceneAnalysisInput` below is this module's own stand-in for "a
StoryScene" -- built by the future composition root (story_pipeline.py),
which alone reads real StoryScene rows and resolves prev-scene context.
`SceneDirectorConfig` is this module's own copy of the tunables that live
on `app.modules.beat.schemas.SceneClassificationProjectConfig`; the
composition root translates one to the other (a few lines), the same way
app/api/v1/endpoints/quality_gate.py builds a QualityAnalysisInput from a
ProjectConfig. "Duplicate the small contract across the boundary, don't
import across it" is the established convention here.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VISUAL_MODES = ("STILL", "STILL_WITH_MOTION", "AI_VIDEO")
VISUAL_PRIORITIES = ("low", "medium", "high")
VISUAL_DENSITIES = ("MINIMAL", "BALANCED", "CINEMATIC")

# Motion preset hints returned per scene -- deliberately the *uppercase*
# names app.modules.beat.schemas.BeatMotionPreset uses (so `.value` maps
# straight onto a Beat when the compiler builds one), NOT
# app.modules.motion.schemas.MotionPresetName's lowercase set. Same
# case-only duplication Beat already does across that boundary.
MOTION_HINTS = (
    "STATIC", "SLOW_PUSH_IN", "SLOW_PULL_OUT", "PAN_LEFT", "PAN_RIGHT",
    "PAN_UP", "PAN_DOWN", "ZOOM_AND_PAN",
)


class SceneAnalysisInput(BaseModel):
    """Everything the classifier needs about one scene, already resolved by
    the composition root -- this module never looks anything up itself.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    order: int
    # StoryScene.scene_type -- a plain string here (HOOK/SETUP/BUILD/REVEAL/
    # CLIMAX/TWIST/REACTION/ENDING/BODY or whatever the Story engine emits);
    # the classifier only special-cases a small set by value, everything
    # else scores as a neutral BODY beat.
    scene_type: str | None = None
    narration: str | None = None
    # Number of distinct spoken lines in StoryScene.dialogue_json (0 = pure
    # narration). Dialogue-heavy scenes read as more "important" (a
    # confrontation), not more "moving".
    dialogue_line_count: int = 0
    emotion: str | None = None
    camera: str | None = None
    character_count: int = 0
    is_chapter_end: bool = False
    duration_hint: float = 6.0
    # Prev-scene continuity, resolved by the composition root. Both False
    # for the first scene of a chapter. Used only for the reuse hint -- a
    # low-importance scene that shares a location and cast with the one
    # before it is a candidate to reuse that scene's image at $0.
    same_location_as_prev: bool = False
    same_characters_as_prev: bool = False

    @field_validator("order")
    @classmethod
    def _order_one_based(cls, value: int) -> int:
        if value < 1:
            raise ValueError("SceneAnalysisInput.order must be >= 1 (1-based)")
        return value

    @field_validator("dialogue_line_count", "character_count")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("count fields must be >= 0")
        return value

    @field_validator("duration_hint")
    @classmethod
    def _duration_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("duration_hint must be > 0")
        return value


class SceneDirectorConfig(BaseModel):
    """The tunables. Mirrors app.modules.beat.schemas.SceneClassificationProjectConfig
    field-for-field (see module docstring). Every default here is the
    BALANCED profile's default.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True

    # Composite score = weighted sum of the 4 sub-scores (each 0-100).
    # Weights sum to 1.0 (validated).
    w_importance: float = 0.35
    w_movement: float = 0.30
    w_emotion: float = 0.20
    w_complexity: float = 0.15

    # Composite cutoffs (0-100). A scene at/above still_motion_threshold
    # gets motion; at/above video_threshold AND with movement_score at/above
    # min_movement_for_video it becomes an AI_VIDEO candidate.
    still_motion_threshold: float = 40.0
    video_threshold: float = 72.0
    min_movement_for_video: float = 55.0

    # Hard budget on AI_VIDEO: after scoring, keep only the top-N candidates
    # such that N <= min(hard_cap, round(ratio * total_scenes)); the rest
    # are demoted to STILL_WITH_MOTION. ratio 0.0 == "never AI_VIDEO".
    ai_video_max_ratio: float = 0.15
    ai_video_hard_cap: int = 12

    # Only affects the STILL vs STILL_WITH_MOTION split for scenes below
    # video_threshold and the reuse hint aggressiveness -- never forces
    # AI_VIDEO. MINIMAL biases toward STATIC + reuse; CINEMATIC biases
    # toward motion. See classifier._density_bias.
    visual_density: str = "BALANCED"

    @field_validator("visual_density")
    @classmethod
    def _known_density(cls, value: str) -> str:
        if value not in VISUAL_DENSITIES:
            raise ValueError(f"Unknown visual_density {value!r}, must be one of {VISUAL_DENSITIES}")
        return value

    @field_validator(
        "w_importance", "w_movement", "w_emotion", "w_complexity",
        "still_motion_threshold", "video_threshold", "min_movement_for_video",
        "ai_video_max_ratio",
    )
    @classmethod
    def _non_negative_float(cls, value: float) -> float:
        if value < 0:
            raise ValueError("must be >= 0")
        return value

    @field_validator("ai_video_max_ratio")
    @classmethod
    def _ratio_within_unit(cls, value: float) -> float:
        if value > 1.0:
            raise ValueError("ai_video_max_ratio must be between 0.0 and 1.0")
        return value

    @field_validator("ai_video_hard_cap")
    @classmethod
    def _cap_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("ai_video_hard_cap must be >= 0")
        return value

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "SceneDirectorConfig":
        total = self.w_importance + self.w_movement + self.w_emotion + self.w_complexity
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"scene-director weights must sum to 1.0, got {total:.3f}")
        if self.still_motion_threshold > self.video_threshold:
            raise ValueError("still_motion_threshold must not exceed video_threshold")
        return self


class SceneClassification(BaseModel):
    """One scene's classification result. `visual_mode` is the decision the
    compiler acts on; the scores are kept for explainability and for a
    human to override against (a user setting StoryScene.visual_mode_source
    = "USER" freezes `visual_mode` so a re-run never touches it).
    """

    model_config = ConfigDict(extra="forbid")

    scene_id: str
    importance_score: int   # 0-100
    movement_score: int     # 0-100
    emotion_score: int      # 0-100
    complexity_score: int   # 0-100
    composite_score: int    # 0-100, the weighted sum
    visual_mode: str        # STILL | STILL_WITH_MOTION | AI_VIDEO
    visual_priority: str    # low | medium | high
    motion_preset_hint: str
    reuse_existing_asset: bool
    estimated_duration: float
    # Why this mode -- one short human-readable line, never relied on for logic.
    reason: str = ""

    @field_validator("visual_mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in VISUAL_MODES:
            raise ValueError(f"Unknown visual_mode {value!r}, must be one of {VISUAL_MODES}")
        return value

    @field_validator("visual_priority")
    @classmethod
    def _known_priority(cls, value: str) -> str:
        if value not in VISUAL_PRIORITIES:
            raise ValueError(f"Unknown visual_priority {value!r}, must be one of {VISUAL_PRIORITIES}")
        return value

    @field_validator("motion_preset_hint")
    @classmethod
    def _known_hint(cls, value: str) -> str:
        if value not in MOTION_HINTS:
            raise ValueError(f"Unknown motion_preset_hint {value!r}, must be one of {MOTION_HINTS}")
        return value


class SceneDirectorReport(BaseModel):
    """The batch result. `ai_video_count` / `still_with_motion_count` /
    `still_count` are convenience rollups; `demoted_scene_ids` names the
    scenes that scored as AI_VIDEO candidates but were pushed down to
    STILL_WITH_MOTION by the ratio/hard-cap budget (surfaced in the UI so a
    user knows why a dramatic scene isn't a video).
    """

    model_config = ConfigDict(extra="forbid")

    scenes: list[SceneClassification] = Field(default_factory=list)
    ai_video_count: int = 0
    still_with_motion_count: int = 0
    still_count: int = 0
    reuse_count: int = 0
    demoted_scene_ids: list[str] = Field(default_factory=list)
