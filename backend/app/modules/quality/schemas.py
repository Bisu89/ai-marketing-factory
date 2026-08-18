"""The Quality Gate domain contract (Task 16 -- see
docs/features/42-content-quality-gate.md and
docs/features/video_factory_architecture.md). A deterministic, local-only
analysis of "is this BeatPlan ready to render" -- narrative structure,
pacing, visual coverage, motion/audio/caption readiness -- with NO
FFmpeg/AI/rendering dependency of its own, exactly like
app.modules.composition is a pure declarative contract rather than a
renderer.

Per app/modules/README.md, this module must never import app.modules.beat,
app.modules.asset, app.modules.batch, app.modules.motion, or
app.modules.video_composer. The pure input contracts below
(BeatAnalysisInput/BeatAssetInfo/QualityAnalysisInput) are this module's
own stand-ins for "a Beat" and "an assigned Asset" -- built by the
composition root (app/api/v1/endpoints/quality_gate.py), which alone is
allowed to read a real BeatPlan and resolve real Asset rows. This mirrors
app.modules.composition.schemas's own CompositionPlan/Scene: this module
owns the *shape* of the analysis input/output, not how to produce one from
live application state.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

# -- Issue codes (section 35) -- stable, for frontend logic; never rely on
# the human-readable `message` for behavior. ------------------------------

ISSUE_CODES = (
    "NO_BEATS",
    "INVALID_BEAT_ORDER",
    "INVALID_BEAT_DURATION",
    "MISSING_VISUAL_ASSET",
    "MISSING_VISUAL_FILE",
    "LOW_VISUAL_CONFIDENCE",
    "LOW_RESOLUTION_ASSET",
    "MISSING_MOTION",
    "MOTION_ARTIFACT_MISSING",
    "AUDIO_MASTER_MISSING",
    "CAPTIONS_ARTIFACT_MISSING",
    "MISSING_NARRATION",
    "DUPLICATE_NARRATION",
    "PACING_OUTLIER",
    "LOW_PURPOSE_DIVERSITY",
    "PURPOSE_DUPLICATION",
    "INVALID_AUDIO_CONFIG",
    "INVALID_CAPTION_CONFIG",
)

SEVERITIES = ("error", "warning")
READINESS_STATUSES = ("READY", "NEEDS_REVIEW", "BLOCKED")
QUALITY_MODES = ("NORMAL", "STRICT")

# Confidence/suitability vocabularies -- the composition root computes the
# actual values (see quality_gate.py's own docstring for why); this module
# only defines the set of valid labels.
ASSET_CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")


class QualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: str
    message: str
    beat_id: str | None = None

    @field_validator("code")
    @classmethod
    def _known_code(cls, value: str) -> str:
        if value not in ISSUE_CODES:
            raise ValueError(f"Unknown issue code {value!r}, must be one of {ISSUE_CODES}")
        return value

    @field_validator("severity")
    @classmethod
    def _known_severity(cls, value: str) -> str:
        if value not in SEVERITIES:
            raise ValueError(f"Unknown severity {value!r}, must be one of {SEVERITIES}")
        return value


class VisualCoverageMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage: float  # beats_with_valid_assets / beats_requiring_visuals, 0.0-1.0
    high_confidence: int = 0
    medium_confidence: int = 0
    low_confidence: int = 0
    missing: int = 0


class QualityDimensions(BaseModel):
    """Each 0-100, always separately visible (section 24 -- "the purpose is
    actionable feedback, not a meaningless number").
    """

    model_config = ConfigDict(extra="forbid")

    narrative: int
    pacing: int
    visual: int
    motion: int
    audio: int
    captions: int


class QualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str  # READY | NEEDS_REVIEW | BLOCKED
    score: int  # 0-100, a production-*readiness* heuristic -- never a virality/performance prediction (section 47)
    dimensions: QualityDimensions
    issues: list[QualityIssue] = Field(default_factory=list)  # severity == "error" -- these are the blockers
    warnings: list[QualityIssue] = Field(default_factory=list)  # severity == "warning" -- non-blocking in NORMAL mode
    visual: VisualCoverageMetrics
    metrics: dict = Field(default_factory=dict)  # supplemental explainability data (e.g. pacing stats)

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str) -> str:
        if value not in READINESS_STATUSES:
            raise ValueError(f"Unknown status {value!r}, must be one of {READINESS_STATUSES}")
        return value


# -- Pure analysis input (built by the composition root) ------------------


class BeatAssetInfo(BaseModel):
    """Everything the analyzer needs to know about one Beat's assigned
    visual asset, already resolved -- this module never looks an asset_id
    up itself (that would require importing app.modules.asset).
    """

    model_config = ConfigDict(extra="forbid")

    has_asset: bool
    asset_valid: bool  # exists in the DB AND file exists AND status != INVALID (section 18)
    asset_confidence: str | None = None  # HIGH/MEDIUM/LOW -- only meaningful when asset_valid
    portrait_suitability: str | None = None  # Task 15's EXCELLENT/GOOD/CROP_REQUIRED/LOW_RESOLUTION

    @field_validator("asset_confidence")
    @classmethod
    def _known_confidence(cls, value: str | None) -> str | None:
        if value is not None and value not in ASSET_CONFIDENCE_LEVELS:
            raise ValueError(f"Unknown confidence {value!r}, must be one of {ASSET_CONFIDENCE_LEVELS}")
        return value


class BeatAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    order: int
    type: str  # Beat "purpose" -- HOOK/SETUP/BUILD/REVEAL/REACTION/ENDING/BODY, a plain string here (see module docstring)
    narration: str | None = None
    duration: float
    visual_hint: str | None = None
    motion_preset: str | None = None  # explicit override, or None to inherit the project default
    asset: BeatAssetInfo
    # Task 23 (see docs/features/49-local-motion-engine.md section 55) --
    # `motion_artifact_checked` is only True when the composition root
    # actually had a real project_id to look a cached clip up against (an
    # arbitrary, unsaved BeatPlan being checked via POST /quality-check has
    # none, and is never penalized for it -- see quality_gate.py's own
    # build_quality_input). `motion_artifact_valid` is meaningless unless
    # `motion_artifact_checked` is True.
    motion_artifact_checked: bool = False
    motion_artifact_valid: bool = True


class ProjectAudioConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narration_enabled: bool = True
    # Task 24 (see docs/features/50-audio-master.md section 55) -- same
    # "only checked when a real project_id was available, only a warning,
    # never a hard block" reasoning as BeatAnalysisInput's own
    # motion_artifact_checked/motion_artifact_valid (Task 23). This is
    # project-level, not per-beat, since audio_master.wav is one artifact
    # for the whole project, not one per beat.
    audio_master_checked: bool = False
    audio_master_valid: bool = True


class ProjectCaptionConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    preset_valid: bool = True
    # Task 25 (see docs/features/51-caption-engine.md section 55) -- same
    # "only checked when a real project_id was available, only a warning,
    # never a hard block" reasoning as ProjectAudioConfigInput's own
    # audio_master_checked/audio_master_valid (Task 24). Project-level, not
    # per-beat, since captions.ass is one artifact for the whole project.
    captions_artifact_checked: bool = False
    captions_artifact_valid: bool = True


class QualityAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beats: list[BeatAnalysisInput] = Field(default_factory=list)
    default_motion_preset: str | None = None  # the project's effective ProjectConfig.motion.default_preset
    audio: ProjectAudioConfigInput = Field(default_factory=ProjectAudioConfigInput)
    captions: ProjectCaptionConfigInput = Field(default_factory=ProjectCaptionConfigInput)
    mode: str = "NORMAL"

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in QUALITY_MODES:
            raise ValueError(f"Unknown mode {value!r}, must be one of {QUALITY_MODES}")
        return value
