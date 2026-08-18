"""Pure domain contracts for the Thumbnail Engine (Task 27 -- see
docs/features/53-thumbnail-metadata-package.md): final.mp4 -> candidate
frames -> deterministic scoring -> best frame -> optional headline ->
thumbnail.jpg. No FFmpeg subprocess calls, no Pillow raster I/O, no
filesystem access beyond what a caller hands in as already-resolved paths
-- mirrors app.modules.caption.schemas' own "pure contracts, business
logic/I-O live in a composition root or this module's own renderer" shape.

Per app/modules/README.md, this module must never import
app.modules.beat/asset/video_composer/factory (or vice versa) -- the
composition root (app/api/v1/endpoints/package_generate.py) is the one
place allowed to translate between this module's own ThumbnailConfig and a
real Project/VideoComposeJob.
"""

from dataclasses import dataclass
from pathlib import Path

THUMBNAIL_GENERATION_FAILED = "THUMBNAIL_GENERATION_FAILED"
THUMBNAIL_INVALID = "THUMBNAIL_INVALID"
THUMBNAIL_NO_VALID_FRAME = "THUMBNAIL_NO_VALID_FRAME"


class ThumbnailError(Exception):
    """Base for every error this module raises -- always carries one of
    the stable codes above so a composition root never has to string-match
    a message to classify a failure.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# Section 6 -- fractional offsets into the video's own duration, not a
# fixed frame count (a 10s video and a 90s video both get candidates
# spread proportionally across their own length). Configurable, not
# hardcoded -- see ThumbnailConfig.candidate_offsets.
DEFAULT_CANDIDATE_OFFSETS = (0.10, 0.25, 0.40, 0.55, 0.70, 0.85)


@dataclass
class FrameStats:
    """Deterministic, measurable image statistics for one candidate frame
    (section 8) -- brightness/contrast/edge-density, computed via plain
    Pillow histogram math, never AI vision (section 7's own "do NOT use AI
    vision for frame scoring").
    """

    offset_fraction: float
    path: Path
    brightness: float  # 0-255, mean grayscale luminance
    contrast: float  # stdev of grayscale luminance
    edge_density: float  # mean intensity of a FIND_EDGES pass -- a sharpness/detail proxy


@dataclass
class ThumbnailConfig:
    """The subset of a project's own render/package settings this module
    actually needs -- this module never imports app.modules.beat (module
    isolation), so the composition root translates.
    """

    width: int
    height: int
    candidate_offsets: tuple[float, ...] = DEFAULT_CANDIDATE_OFFSETS
    headline_enabled: bool = True
    headline_text: str | None = None
    headline_max_chars: int = 40
