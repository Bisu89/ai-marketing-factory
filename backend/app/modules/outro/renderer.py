"""Local ffmpeg renderer for the Outro Card (see schemas.py's own
docstring for what/why). No shared ffmpeg wrapper exists anywhere in this
codebase (see app/modules/motion/renderer.py's own docstring) -- this file
runs its own subprocess.run(["ffmpeg", ...]) calls, following that same
established convention rather than inventing a cross-module one.

Typewriter reveal technique: ffmpeg has no built-in "reveal text over
time" primitive, so this chains one `drawtext` filter per revealed
prefix of each line, each active for a non-overlapping
`enable='between(t,start,end)'` window (a standard, widely-documented
ffmpeg hack for this exact effect) -- except each line's *final*,
fully-revealed state stays active through the end of the clip, so
earlier lines don't disappear once a later line starts typing.

Line-wrapping uses real glyph measurement via Pillow (already a core
dependency -- see app/modules/asset/ingest.py's own Image usage) rather
than a chars-per-line guess: an early guess-based version overflowed the
frame width badly during this feature's own real ffmpeg testing.
Embedding a literal newline directly inside one drawtext `text=` value
was also tried and rejected -- ffmpeg's drawtext renders a stray glyph
box for it (confirmed during testing); separate per-line filters with
computed y-offsets avoid that entirely.
"""

import shutil
import subprocess
from pathlib import Path

from PIL import ImageFont

from app.core.exceptions import FileOperationError
from app.modules.outro.schemas import OutroError

FONT_PATH = "C:/Windows/Fonts/arial.ttf"
# ffmpeg's filter-graph parser treats ':' as an option separator even
# inside single-quoted values (confirmed: real ffmpeg failure during this
# feature's own testing, "No option name near '/Windows/Fonts/arial.ttf...'")
# -- same fix as video_composer/service.py's own _escape_for_ffmpeg_filter
# for the identical Windows-drive-letter-colon situation.
_FONT_PATH_ESCAPED = FONT_PATH.replace(":", "\\:")

_FONT_SIZE_DIVISOR = 32  # font_size = height / this
_LINE_SPACING_RATIO = 1.4
_MAX_TEXT_WIDTH_RATIO = 0.85  # leave a margin either side of the frame
_REVEAL_FRACTION = 0.7  # reveal finishes within this fraction of duration_sec, then holds


def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def _wrap_lines(text: str, font: ImageFont.FreeTypeFont, max_width_px: float) -> list[str]:
    """Real-glyph-measured word wrap (font.getlength) -- not a
    chars-per-line guess, which overflowed the frame in this feature's
    own real ffmpeg testing (font metrics vary a lot with character mix).
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and font.getlength(candidate) > max_width_px:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _reveal_tokens(text: str) -> list[str]:
    """Splits into the units the character-reveal loop must never cut
    across mid-sequence: every escape _escape_drawtext produces (`\\\\`,
    `\\'`, `\\:`, `\\%`) is exactly backslash + one character. A prefix
    ending in a lone backslash right before the filter string's closing
    quote breaks ffmpeg's parser entirely (confirmed: real ffmpeg failure
    during this feature's own testing) -- slicing by these tokens instead
    of raw string indices makes that impossible by construction.
    """
    tokens: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            tokens.append(text[i : i + 2])
            i += 2
        else:
            tokens.append(text[i])
            i += 1
    return tokens


def render_outro_clip(
    text: str,
    duration_sec: float,
    width: int,
    height: int,
    fps: float,
    output_path: Path,
    bgm_path: Path | None = None,
    bgm_start_volume: float = 0.15,
) -> None:
    """Black background + character-by-character CTA reveal + (if bgm_path
    given) background music swelling from bgm_start_volume up to 1.0
    (full volume) across the whole clip -- the "outro" duration IS the
    swell duration, matching the real user request this feature came
    from. Silent audio when no bgm_path is given (music disabled/none
    resolved for this project) -- nothing to swell.
    """
    if not text.strip():
        raise OutroError("Outro text must not be blank.")
    if shutil.which("ffmpeg") is None:
        raise FileOperationError("ffmpeg was not found on PATH -- is it installed/bundled?")

    font_size = max(28, height // _FONT_SIZE_DIVISOR)
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except OSError as exc:
        raise OutroError(f"Could not load font for outro text: {FONT_PATH} ({exc})") from exc

    lines = _wrap_lines(text.strip(), font, width * _MAX_TEXT_WIDTH_RATIO)
    line_height = font_size * _LINE_SPACING_RATIO
    block_top = (height - len(lines) * line_height) / 2

    escaped_lines = [_escape_drawtext(line) for line in lines]
    line_tokens = [_reveal_tokens(line) for line in escaped_lines]
    total_chars = sum(len(tokens) for tokens in line_tokens) or 1

    reveal_span = max(0.5, min(duration_sec * _REVEAL_FRACTION, total_chars * 0.08))
    char_interval = reveal_span / total_chars

    drawtext_filters: list[str] = []
    elapsed_chars = 0
    for line_index, tokens in enumerate(line_tokens):
        y = block_top + line_index * line_height
        for i in range(1, len(tokens) + 1):
            prefix = "".join(tokens[:i])
            start = (elapsed_chars + i - 1) * char_interval
            is_last_char_of_last_line = line_index == len(line_tokens) - 1 and i == len(tokens)
            end = duration_sec if is_last_char_of_last_line else (elapsed_chars + i) * char_interval
            drawtext_filters.append(
                f"drawtext=fontfile='{_FONT_PATH_ESCAPED}':text='{prefix}':fontsize={font_size}:fontcolor=white:"
                f"x=(w-text_w)/2:y={y:.1f}:"
                f"enable='between(t,{start:.4f},{end:.4f})'"
            )
        # This line's fully-revealed state persists for the rest of the
        # clip (open-ended enable) so it doesn't vanish once the next
        # line starts typing underneath it.
        if tokens:
            full_line = "".join(tokens)
            next_line_start = (elapsed_chars + len(tokens)) * char_interval
            drawtext_filters.append(
                f"drawtext=fontfile='{_FONT_PATH_ESCAPED}':text='{full_line}':fontsize={font_size}:fontcolor=white:"
                f"x=(w-text_w)/2:y={y:.1f}:"
                f"enable='gte(t,{next_line_start:.4f})'"
            )
        elapsed_chars += len(tokens)

    video_filters = ",".join(drawtext_filters)

    inputs = [
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration_sec}:r={fps}",
    ]
    if bgm_path is not None:
        inputs += ["-stream_loop", "-1", "-i", str(bgm_path)]
    else:
        inputs += ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration_sec}"]

    audio_filter = (
        f"[1:a]volume=eval=frame:volume='{bgm_start_volume:.4f}+"
        f"({1.0 - bgm_start_volume:.4f})*(t/{duration_sec:.4f})'[aout]"
        if bgm_path is not None
        else "[1:a]anull[aout]"
    )

    filter_complex = f"[0:v]{video_filters}[vout];{audio_filter}"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration_sec}",
        str(output_path),
    ]
    try:
        process = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise FileOperationError("ffmpeg was not found on PATH -- is it installed/bundled?") from exc

    if process.returncode != 0:
        raise OutroError(f"ffmpeg failed to render the outro clip: {process.stderr.strip()[-2000:]}")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise OutroError(f"ffmpeg reported success but produced no output file: {output_path}")
