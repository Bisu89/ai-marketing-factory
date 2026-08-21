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

# Long enough for a real CTA ("Follow for part 2", "Comment your story
# below") without letting the character-reveal filter chain (one ffmpeg
# drawtext filter per revealed character) grow unreasonably large.
MAX_OUTRO_TEXT_LENGTH = 80


class OutroError(Exception):
    """Raised for a genuine outro-rendering failure (ffmpeg missing/
    failing, unreadable BGM input) -- same shape as this codebase's other
    per-module Error classes (AudioError, ImageGenError, CaptionError).
    """
