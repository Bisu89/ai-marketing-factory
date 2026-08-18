"""The Final QA domain contract (Task 28 -- see
docs/features/54-final-qa.md). A deterministic, local-only, READ-ONLY
analysis of "is this project's finished package genuinely safe to post" --
video/audio/thumbnail/metadata/caption integrity plus cross-artifact
freshness -- with no FFmpeg/AI dependency of its own, mirroring
app.modules.quality's own "pure contract, business logic lives in a
composition root" shape (see that module's own docstring).

Per app/modules/README.md, this module must never import app.modules.beat,
app.modules.asset, app.modules.video_composer, app.modules.audio,
app.modules.caption, app.modules.thumbnail, or app.modules.metadata. The
pure input contract below (QAInput) is this module's own stand-in for
"a rendered, packaged project" -- built by the composition root
(app/api/v1/endpoints/final_qa.py), which alone is allowed to read a real
Project/VideoComposeJob/render_metadata.json/package files.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field, field_validator

# -- Check codes (section 47/50) -- stable, for frontend logic and for
# "owner"/repair-stage routing (section 40/41); never rely on the human-
# readable `message` for behavior. Reuses existing codes from earlier
# tasks where one already exists for the exact same condition (e.g.
# FINAL_DURATION_MISMATCH from Task 26, AUDIO_SILENT from Task 24,
# THUMBNAIL_INVALID/PACKAGE_INCOMPLETE from Task 27) rather than minting a
# second, disagreeing name for the same problem. ---------------------------

CHECK_CODES = (
    "PACKAGE_INCOMPLETE",
    "FINAL_VIDEO_MISSING",
    "FINAL_VIDEO_INVALID",
    "FINAL_STREAM_INVALID",
    "FINAL_RESOLUTION_MISMATCH",
    "FINAL_FPS_MISMATCH",
    "FINAL_DURATION_MISMATCH",
    "AUDIO_SILENT",
    "AUDIO_CLIPPING",
    "THUMBNAIL_INVALID",
    "THUMBNAIL_LOW_QUALITY",
    "METADATA_INVALID",
    "CAPTIONS_INVALID",
    "CAPTIONS_TIMING_INVALID",
    "BEAT_ARTIFACT_MISSING",
    "STALE_DEPENDENCY",
    "STALE_RENDER_VERSION",
    "STALE_PACKAGE_VERSION",
)

CHECK_STATUSES = ("PASS", "WARN", "FAIL")
SEVERITIES = ("info", "warning", "error")
QA_STATUSES = ("PASS", "PASS_WITH_WARNINGS", "FAIL")

# Section 40 -- which upstream stage a failing check most likely needs
# repairing at. A plain label, not a FACTORY_STAGES value (QA's own repair
# routing is coarser -- "go fix Audio," not "resume exactly at
# GENERATING_AUDIO's own sub-step").
REPAIR_STAGES = ("RENDER", "AUDIO", "THUMBNAIL", "PACKAGE", "CAPTIONS", "MOTION", "UNKNOWN")


class QACheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    code: str
    status: str  # PASS | WARN | FAIL
    severity: str  # info | warning | error
    message: str
    actual: str | None = None
    expected: str | None = None
    repair_stage: str | None = None  # only meaningful when status != PASS

    @field_validator("code")
    @classmethod
    def _known_code(cls, value: str) -> str:
        if value not in CHECK_CODES:
            raise ValueError(f"Unknown check code {value!r}, must be one of {CHECK_CODES}")
        return value

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str) -> str:
        if value not in CHECK_STATUSES:
            raise ValueError(f"Unknown check status {value!r}, must be one of {CHECK_STATUSES}")
        return value

    @field_validator("severity")
    @classmethod
    def _known_severity(cls, value: str) -> str:
        if value not in SEVERITIES:
            raise ValueError(f"Unknown severity {value!r}, must be one of {SEVERITIES}")
        return value

    @field_validator("repair_stage")
    @classmethod
    def _known_repair_stage(cls, value: str | None) -> str | None:
        if value is not None and value not in REPAIR_STAGES:
            raise ValueError(f"Unknown repair_stage {value!r}, must be one of {REPAIR_STAGES}")
        return value


class QAReport(BaseModel):
    """Section 4/44 -- deliberately close to app.modules.quality.schemas.
    QualityReport's own shape (status/score/checks), since this codebase
    already established that exact vocabulary for "is this thing ready."
    """

    model_config = ConfigDict(extra="forbid")

    status: str  # PASS | PASS_WITH_WARNINGS | FAIL
    score: int  # 0-100, informational only -- never overrides a FAIL (section 45)
    checks: list[QACheck] = Field(default_factory=list)
    project_id: int | None = None
    pipeline_version: str = "final-qa-v1"
    started_at: str | None = None  # ISO 8601 -- pure module, no datetime.now() of its own
    completed_at: str | None = None

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str) -> str:
        if value not in QA_STATUSES:
            raise ValueError(f"Unknown status {value!r}, must be one of {QA_STATUSES}")
        return value

    @property
    def failures(self) -> list[QACheck]:
        return [c for c in self.checks if c.status == "FAIL"]

    @property
    def warnings(self) -> list[QACheck]:
        return [c for c in self.checks if c.status == "WARN"]


# -- Pure analysis input (built by the composition root) -------------------


@dataclass
class VideoStreamInfo:
    duration: float
    width: int
    height: int
    fps: float
    video_streams: int
    audio_streams: int
    video_codec: str | None
    audio_codec: str | None
    pix_fmt: str | None
    file_exists: bool
    file_size: int


@dataclass
class AudioLevelInfo:
    """Mean/max volume in dB (ffmpeg's own `volumedetect` output) -- the
    same measurement app.modules.audio.renderer already uses for its own
    AUDIO_SILENT check (Task 24), duplicated here per module isolation,
    not a real LUFS/true-peak measurement (see this module's own
    renderer.py docstring for why).
    """

    mean_volume_db: float | None
    max_volume_db: float | None
    probed: bool  # False when the audio track couldn't be analyzed at all


@dataclass
class ThumbnailInfo:
    exists: bool
    width: int | None
    height: int | None
    expected_width: int
    expected_height: int
    file_size: int
    is_low_quality: bool  # section 21 -- brightness/contrast/edge-density re-check against the SAVED image


@dataclass
class MetadataInfo:
    exists: bool
    parses: bool
    title: str | None
    description: str | None
    hashtags: list[str] | None
    referenced_video: str | None
    referenced_thumbnail: str | None


@dataclass
class CaptionsInfo:
    enabled: bool
    exists: bool
    parses: bool
    dialogue_count: int
    max_end_time: float | None


@dataclass
class BeatCompletenessInfo:
    total_beats: int
    beats_with_motion_artifact: int
    order_is_contiguous: bool


@dataclass
class DependencyFreshnessInfo:
    """Section 32/33 -- a real mtime comparison (see this module's own
    renderer.py docstring for why fingerprints aren't available to compare
    instead). `*_is_newer_than_video` is True (stale) when that upstream
    artifact's own mtime is *after* final.mp4's own mtime -- i.e. it
    changed since the video that's supposed to reflect it was produced.
    None means "that artifact doesn't apply to this project" (e.g.
    captions disabled), never treated as stale.
    """

    audio_master_is_newer_than_video: bool | None
    captions_is_newer_than_video: bool | None


@dataclass
class VersionInfo:
    package_engine_version: str | None
    current_package_engine_version: str


@dataclass
class QAInput:
    """The composition root's own single, fully-resolved snapshot of
    everything Final QA needs -- one real ffprobe/volumedetect/file-read
    pass each, never re-run mid-analysis (section 48's own "QA should be
    cheap").
    """

    project_id: int
    package_exists: bool
    package_error_message: str | None
    video: VideoStreamInfo | None
    expected_width: int
    expected_height: int
    expected_fps: float
    expected_duration: float | None
    audio_level: AudioLevelInfo | None
    narration_enabled: bool
    thumbnail: ThumbnailInfo | None
    metadata: MetadataInfo | None
    captions: CaptionsInfo
    beats: BeatCompletenessInfo
    dependencies: DependencyFreshnessInfo
    version: VersionInfo
