"""Pure domain contracts for the Outro Card (real user report: videos cut
off abruptly the instant narration ends, no room for a proper closing
CTA). A short, silent-narration trailing segment appended after the main
composed video: solid black background, a manually-typed CTA revealed
character-by-character, background music swelling up to full volume --
never AI-generated, never derived from the beat script.
"""

MIN_OUTRO_DURATION_SEC = 5.0
MAX_OUTRO_DURATION_SEC = 7.0
DEFAULT_OUTRO_DURATION_SEC = 6.0

# Real user report: felt needlessly restrictive at 80 once the renderer
# (this module's own render_outro_clip -> _fit_text) properly auto-wraps
# AND shrinks font size to guarantee the block always fits the frame --
# raised now that overflow is no longer a risk. Still bounded, not
# unlimited: a real ffmpeg filter chain has one drawtext filter per
# revealed character, and a multi-paragraph CTA stops being a "quick CTA"
# at some point anyway. Kept in sync with beat/schemas.py's own copy
# (duplicated, not imported -- module isolation; that one is what's
# actually enforced end-to-end).
MAX_OUTRO_TEXT_LENGTH = 200


class OutroError(Exception):
    """Raised for a genuine outro-rendering failure (ffmpeg missing/
    failing, unreadable BGM input) -- same shape as this codebase's other
    per-module Error classes (AudioError, ImageGenError, CaptionError).
    """
