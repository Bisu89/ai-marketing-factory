"""Pure domain contracts for the Audio Master (Task 24 -- see
docs/features/50-audio-master.md): narration + optional local BGM, ducked
and mixed into one deterministic audio artifact. No SQLAlchemy, no
FastAPI, no filesystem access beyond what a caller hands in as
already-resolved paths -- mirrors app.modules.motion.schemas' own "pure
contracts, business logic lives in a composition root" shape.

Per app/modules/README.md, this module must never import
app.modules.beat/asset/voice/factory/video_composer (or vice versa) -- the
composition root (app/api/v1/endpoints/audio_generate.py) is the one place
allowed to translate between this module's own AudioMixPlan and a real
Project/Beat/Asset.
"""

from dataclasses import dataclass, field

# -- Error codes (section 52) -- stable, machine-readable, never a raw
# ffmpeg stack trace surfaced to the UI. -------------------------------

AUDIO_MIX_FAILED = "AUDIO_MIX_FAILED"
BGM_NOT_FOUND = "BGM_NOT_FOUND"
BGM_INVALID = "BGM_INVALID"
AUDIO_OUTPUT_INVALID = "AUDIO_OUTPUT_INVALID"
AUDIO_CLIPPING = "AUDIO_CLIPPING"
AUDIO_SILENT = "AUDIO_SILENT"
AUDIO_DURATION_MISMATCH = "AUDIO_DURATION_MISMATCH"


class AudioError(Exception):
    """Base for every error this module raises -- always carries one of
    the stable codes above so a composition root never has to string-match
    a message to classify a failure.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class AudioMixPlan:
    """A fully-parameterized, renderable mix instruction -- purely
    declarative, nothing here renders anything (see renderer.py for that).
    `bgm_path` is None for narration-only output (section 9: BGM off is a
    real, first-class mode, never a silent placeholder track).
    """

    narration_path: str
    target_duration: float
    bgm_path: str | None = None
    narration_volume: float = 1.0
    bgm_volume: float = 0.15
    ducking_enabled: bool = True
    ducking_ratio: float = 8.0
    fade_in_sec: float = 0.5
    fade_out_sec: float = 1.0


@dataclass
class AudioProbe:
    duration_sec: float
    sample_rate: int
    channels: int
    codec: str
    mean_volume_db: float | None
    max_volume_db: float | None


@dataclass
class BgmCandidate:
    """One local Asset the composition root considers eligible BGM --
    deliberately NOT app.modules.asset.models.Asset itself (module
    isolation, see module docstring); the composition root translates.
    """

    asset_id: int
    path: str
    duration_sec: float | None
    tags: list[str] = field(default_factory=list)
