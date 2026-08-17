"""Pure domain contracts for the Voice Factory (Task 22 -- see
docs/features/48-voice-factory-local-tts.md): TTS synthesis results, word
timing, and per-beat timing. No SQLAlchemy, no FastAPI, no filesystem
access beyond what a caller hands in as already-resolved paths -- mirrors
app.modules.beat.schemas' own "pure Pydantic/dataclass contracts, business
logic lives in a composition root" shape.

Per app/modules/README.md, this module must never import
app.modules.beat/asset/factory/video_composer/ai (or vice versa) -- the
composition root (app/api/v1/endpoints/voice_generate.py) is the one place
allowed to translate between this module's own BeatTimingInput/BeatTiming
and app.modules.beat.schemas.Beat.
"""

from dataclasses import dataclass, field

# -- Error codes (section 38) -- stable, machine-readable, never a raw
# provider stack trace surfaced to the UI. ------------------------------

TTS_PROVIDER_UNAVAILABLE = "TTS_PROVIDER_UNAVAILABLE"
TTS_GENERATION_FAILED = "TTS_GENERATION_FAILED"
TTS_INVALID_OUTPUT = "TTS_INVALID_OUTPUT"
VOICE_SILENT = "VOICE_SILENT"
VOICE_FORMAT_INVALID = "VOICE_FORMAT_INVALID"
VOICE_TIMING_FAILED = "VOICE_TIMING_FAILED"


class VoiceError(Exception):
    """Base for every error this module raises -- always carries one of the
    stable codes above so a composition root never has to string-match a
    message to classify a failure.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class WordTiming:
    """One spoken word's position in an audio file, in seconds. Only ever
    populated by a provider that genuinely exposes this (edge-tts's own
    WordBoundary events, see providers.py) -- section 16's "priority 1"
    timing source. A provider that can't supply this (the default local
    engine) simply returns an empty list, not fabricated values.
    """

    text: str
    start: float
    end: float


@dataclass
class AudioResult:
    """What a TTSProvider hands back after a real, successful synthesis --
    never returned for a partial/failed attempt (see providers.py's own
    atomic-write convention).
    """

    path: str
    duration_sec: float
    sample_rate: int
    channels: int
    word_timestamps: list[WordTiming] = field(default_factory=list)


@dataclass
class AudioProbe:
    """Section 34's minimum audio analysis -- duration/format facts plus a
    coarse loudness signal (mean/max dBFS) used only to detect near-total
    silence (section 36), not full LUFS/true-peak metering (section 35:
    optional, explicitly not required for the MVP).
    """

    duration_sec: float
    sample_rate: int
    channels: int
    codec: str
    mean_volume_db: float | None
    max_volume_db: float | None


@dataclass
class BeatTimingInput:
    """One Beat's worth of input the timing algorithm needs -- deliberately
    NOT app.modules.beat.schemas.Beat itself (module isolation, see module
    docstring); the composition root translates.
    """

    beat_id: str
    text: str


@dataclass
class BeatTiming:
    beat_id: str
    start: float
    end: float
    duration: float
