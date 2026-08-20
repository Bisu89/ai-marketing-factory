"""Pure domain contracts for the Caption Engine (Task 25 -- see
docs/features/51-caption-engine.md): Script + Beat/voice timing -> caption
segments -> a styled ASS subtitle. No SQLAlchemy, no FastAPI, no
filesystem access beyond what a caller hands in as already-resolved paths
-- mirrors app.modules.motion/audio.schemas' own "pure contracts, business
logic lives in a composition root" shape.

Per app/modules/README.md, this module must never import
app.modules.beat/asset/voice/factory/video_composer (or vice versa) -- the
composition root (app/api/v1/endpoints/caption_generate.py) is the one
place allowed to translate between this module's own CaptionSegment and a
real Project/Beat.
"""

from dataclasses import dataclass

# -- Error codes (section 48) -- stable, machine-readable, never a raw
# parser/ffmpeg stack trace surfaced to the UI. -------------------------

CAPTION_GENERATION_FAILED = "CAPTION_GENERATION_FAILED"
CAPTION_TIMING_INVALID = "CAPTION_TIMING_INVALID"
CAPTION_TEXT_INVALID = "CAPTION_TEXT_INVALID"
CAPTION_ASS_INVALID = "CAPTION_ASS_INVALID"
CAPTION_STYLE_INVALID = "CAPTION_STYLE_INVALID"
CAPTION_GLYPH_UNSUPPORTED = "CAPTION_GLYPH_UNSUPPORTED"


class CaptionError(Exception):
    """Base for every error this module raises -- always carries one of
    the stable codes above so a composition root never has to string-match
    a message to classify a failure.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class CaptionSegment:
    """One on-screen caption -- deliberately NOT one Dialogue-per-word (no
    per-word timing exists for pre-recorded local narration, see
    segmentation.py's own module docstring) and deliberately NOT a
    duplicate of Beat's own timing model (section 4: "the Beat remains the
    source of truth for Beat boundaries") -- `beat_id` + `start`/`end`
    (absolute, same timeline as Beat.start/end) is a real sub-window of one
    Beat, never spanning across two.
    """

    id: str
    beat_id: str
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class CaptionWordTiming:
    """One spoken word's real, measured position (absolute seconds, same
    timeline as Beat.start/end) -- mirrors app.modules.voice.schemas.
    WordTiming by shape, duplicated rather than imported (module
    isolation, same convention as CAPTION_PRESETS elsewhere in this
    codebase). Only ever populated for a provider that genuinely exposes
    per-word boundaries (edge_tts); Task 62 (see docs/features/
    62-caption-real-word-timing.md) is what lets segmentation.py use this
    instead of a generic weighted-text-length estimate, when available.
    """

    text: str
    start: float
    end: float


@dataclass
class CaptionSegmentationConfig:
    """The subset of CaptionsProjectConfig (app.modules.beat.schemas) that
    segmentation.py actually needs -- this module never imports that
    module (module isolation), so the composition root translates.
    """

    max_words: int = 7
    max_chars: int = 42
    min_duration_sec: float = 0.8
    max_duration_sec: float = 3.5
    reading_speed_wps: float = 3.3
