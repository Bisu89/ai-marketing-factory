"""Word-timed caption rendering for the Video Composer's own render path
(ASS burned in + a plain SRT sidecar).

Extracted verbatim from `VideoComposerService` (P2 refactor -- see
docs/features/141). Behaviour is unchanged: all 5 presets share the same
word-boundary timing data and the same `_split_line_for_width` row
wrapping; only the Dialogue layout strategy and the ASS Style differ.

This is `video_composer`'s own copy -- `app.modules.caption.ass_writer` is
the separate Factory-pipeline implementation and the two stay independent
by the codebase's "duplicate, don't import across modules" convention.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import ImageFont

from app.modules.video_composer.models import CAPTION_PRESETS

FONT_PATH = "C:/Windows/Fonts/arial.ttf"
# The karaoke subtitle style below renders Bold=1, so word widths must be
# measured with the bold metrics or the highlight box drifts off the word.
FONT_PATH_BOLD = "C:/Windows/Fonts/arialbd.ttf"

MAX_WORDS_PER_LINE = 5
MAX_LINE_DURATION_SEC = 4.5
LINE_BREAK_GAP_SEC = 0.6

# Background box colour behind the word currently being spoken. Text itself
# always stays white -- ASS &HBBGGRR& order (reversed from usual RRGGBB).
HIGHLIGHT_COLORS = [
    "00FFFF", "FFFF00", "9314FF", "00A5FF", "32CD32", "00D7FF", "FF6EC7", "F0E000",
]

# Per-preset caption styling. `alignment`/`margin_v_frac` use ASS's own
# numpad alignment convention: 2 = bottom-center, 5 = middle-center,
# 8 = top-center. `font_scale` multiplies the caller-supplied base
# font_size, so "big_statement" reads as dramatically larger without a
# second font-sizing system.
CAPTION_PRESET_CONFIG = {
    "emotional": {"font_bold": True, "italic": False, "font_scale": 1.0, "margin_v_frac": 0.11, "alignment": 2},
    "cinematic": {"font_bold": False, "italic": False, "font_scale": 0.85, "margin_v_frac": 0.08, "alignment": 2},
    "word_highlight": {"font_bold": True, "italic": False, "font_scale": 1.0, "margin_v_frac": 0.11, "alignment": 2},
    "big_statement": {"font_bold": True, "italic": False, "font_scale": 1.8, "margin_v_frac": 0.45, "alignment": 5},
    "quote": {"font_bold": False, "italic": True, "font_scale": 0.9, "margin_v_frac": 0.45, "alignment": 5},
    "top": {"font_bold": True, "italic": False, "font_scale": 0.85, "margin_v_frac": 0.09, "alignment": 8},
}
assert set(CAPTION_PRESET_CONFIG) == set(CAPTION_PRESETS)


def group_words_into_lines(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        if current:
            gap = word["start"] - current[-1]["end"]
            would_be_duration = word["end"] - current[0]["start"]
            if (
                gap > LINE_BREAK_GAP_SEC
                or len(current) >= MAX_WORDS_PER_LINE
                or would_be_duration > MAX_LINE_DURATION_SEC
            ):
                lines.append(current)
                current = []
        current.append(word)
    if current:
        lines.append(current)
    return lines


def _format_ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _rounded_rect_drawing(w: float, h: float, r: float) -> str:
    """ASS \\p vector-drawing path for a filled rounded rectangle spanning
    (0,0) to (w,h) -- used as the highlight box behind the active word."""
    r = min(r, w / 2, h / 2)
    return (
        f"m {r:.1f} 0 "
        f"l {w - r:.1f} 0 "
        f"b {w:.1f} 0 {w:.1f} 0 {w:.1f} {r:.1f} "
        f"l {w:.1f} {h - r:.1f} "
        f"b {w:.1f} {h:.1f} {w:.1f} {h:.1f} {w - r:.1f} {h:.1f} "
        f"l {r:.1f} {h:.1f} "
        f"b 0 {h:.1f} 0 {h:.1f} 0 {h - r:.1f} "
        f"l 0 {r:.1f} "
        f"b 0 0 0 0 {r:.1f} 0"
    )


def _split_line_for_width(
    line: list[dict], font: ImageFont.FreeTypeFont, space_width: float, available_width: float
) -> list[list[dict]]:
    """Re-break a line's words wherever the cumulative rendered width would
    exceed the box a single unwrapped row can occupy. The box layout below
    assumes each `line` renders on exactly one row -- libass's own auto-wrap
    can't be relied on for that -- so wrapping has to happen here, using the
    same width math."""
    rows: list[list[dict]] = []
    current: list[dict] = []
    current_width = 0.0
    for word in line:
        word_width = font.getlength(word["text"])
        added = word_width if not current else word_width + space_width
        if current and current_width + added > available_width:
            rows.append(current)
            current = []
            added = word_width
            current_width = 0.0
        current.append(word)
        current_width += added
    if current:
        rows.append(current)
    return rows


def write_subtitles(
    lines: list[list[dict]],
    ass_path: Path,
    srt_path: Path,
    width: int,
    height: int,
    font_size: int,
    caption_preset: str = "emotional",
) -> None:
    """Burns word-timed captions to `ass_path` (+ a plain `srt_path`
    alongside, unchanged regardless of preset), styled per `caption_preset`.
    "emotional" is the original karaoke-highlight-box behavior.
    """
    if caption_preset not in CAPTION_PRESET_CONFIG:
        raise ValueError(f"Unknown caption preset {caption_preset!r}, must be one of {CAPTION_PRESETS}")
    config = CAPTION_PRESET_CONFIG[caption_preset]

    scaled_font_size = max(20, int(font_size * config["font_scale"]))
    font_path = FONT_PATH_BOLD if config["font_bold"] else FONT_PATH
    font = ImageFont.truetype(font_path, scaled_font_size)
    space_width = font.getlength(" ")
    margin_x = 40
    margin_v = int(height * config["margin_v_frac"])
    available_width = width - 2 * margin_x

    if caption_preset == "emotional":
        ass_lines = _ass_events_emotional(
            lines, font, space_width, available_width, width, margin_v, scaled_font_size
        )
    elif caption_preset == "word_highlight":
        ass_lines = _ass_events_word_highlight(lines, font, space_width, available_width)
    elif caption_preset in ("cinematic", "top"):
        # "top" is the same plain static-line layout as "cinematic" -- only
        # the Style's alignment/margin/font_scale differ.
        ass_lines = _ass_events_static_lines(lines, font, space_width, available_width)
    elif caption_preset == "big_statement":
        ass_lines = _ass_events_big_statement(lines)
    else:  # "quote"
        ass_lines = _ass_events_quote(lines, font, space_width, available_width)

    style_line = (
        f"Style: Karaoke,Arial,{scaled_font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        f"{1 if config['font_bold'] else 0},{1 if config['italic'] else 0},0,0,100,100,0,0,1,3,0,"
        f"{config['alignment']},{margin_x},{margin_x},{margin_v},1"
    )
    ass_content = (
        f"""[Script Info]
Title: Phu de {caption_preset}
ScriptType: v4.00+
WrapStyle: 2
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        + "\n".join(ass_lines)
        + "\n"
    )
    ass_path.write_text(ass_content, encoding="utf-8")

    srt_lines = []
    for i, line in enumerate(lines, start=1):
        plain_text = " ".join(word["text"] for word in line)
        srt_lines.append(
            f"{i}\n{_format_srt_time(line[0]['start'])} --> "
            f"{_format_srt_time(line[-1]['end'])}\n{plain_text}\n"
        )
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")


def _ass_events_emotional(
    lines: list[list[dict]],
    font: ImageFont.FreeTypeFont,
    space_width: float,
    available_width: float,
    width: int,
    margin_v: int,
    font_size: int,
) -> list[str]:
    """The original karaoke-highlight-box preset (see
    17-karaoke-highlight-box.md), unchanged: a solid rounded box slides
    behind whichever word is being spoken; text itself stays plain white."""
    box_height = font_size * 1.35
    box_top = margin_v - font_size * 0.14
    pad_x = font_size * 0.22
    radius = font_size * 0.22

    ass_lines = []
    for line in lines:
        for row in _split_line_for_width(line, font, space_width, available_width):
            row_start = row[0]["start"]
            row_end = row[-1]["end"]
            plain_text = " ".join(word["text"] for word in row)

            word_widths = [font.getlength(word["text"]) for word in row]
            total_width = sum(word_widths) + space_width * (len(row) - 1)
            cursor_x = width / 2 - total_width / 2
            color = random.choice(HIGHLIGHT_COLORS)
            for word, word_width in zip(row, word_widths):
                box_x = cursor_x - pad_x
                box_w = word_width + pad_x * 2
                drawing = _rounded_rect_drawing(box_w, box_height, radius)
                ass_lines.append(
                    f"Dialogue: 0,{_format_ass_time(word['start'])},{_format_ass_time(word['end'])},"
                    f"Karaoke,,0,0,0,,{{\\an7\\pos({box_x:.1f},{box_top:.1f})\\bord0\\shad0"
                    f"\\1c&H{color}&\\1a&H00&\\p1}}{drawing}{{\\p0}}"
                )
                cursor_x += word_width + space_width

            ass_lines.append(
                f"Dialogue: 1,{_format_ass_time(row_start)},{_format_ass_time(row_end)},"
                f"Karaoke,,0,0,0,,{plain_text}"
            )
    return ass_lines


def _ass_events_word_highlight(
    lines: list[list[dict]],
    font: ImageFont.FreeTypeFont,
    space_width: float,
    available_width: float,
) -> list[str]:
    """Simpler alternative to "emotional": no box, just recolours the
    active word inline within the row's own text via an ASS `\\c` override,
    reset back to white immediately after."""
    ass_lines = []
    for line in lines:
        for row in _split_line_for_width(line, font, space_width, available_width):
            words_text = [word["text"] for word in row]
            for i, word in enumerate(row):
                color = random.choice(HIGHLIGHT_COLORS)
                rendered = " ".join(
                    f"{{\\c&H{color}&}}{text}{{\\c&HFFFFFF&}}" if j == i else text
                    for j, text in enumerate(words_text)
                )
                ass_lines.append(
                    f"Dialogue: 0,{_format_ass_time(word['start'])},{_format_ass_time(word['end'])},"
                    f"Karaoke,,0,0,0,,{rendered}"
                )
    return ass_lines


def _ass_events_static_lines(
    lines: list[list[dict]],
    font: ImageFont.FreeTypeFont,
    space_width: float,
    available_width: float,
) -> list[str]:
    """"cinematic" preset: clean movie-subtitle look -- one static Dialogue
    per row spanning its whole start..end span, no per-word animation."""
    ass_lines = []
    for line in lines:
        for row in _split_line_for_width(line, font, space_width, available_width):
            plain_text = " ".join(word["text"] for word in row)
            ass_lines.append(
                f"Dialogue: 0,{_format_ass_time(row[0]['start'])},{_format_ass_time(row[-1]['end'])},"
                f"Karaoke,,0,0,0,,{plain_text}"
            )
    return ass_lines


def _ass_events_big_statement(lines: list[list[dict]]) -> list[str]:
    """"big_statement" preset: one or two words at a time, upper-cased, for
    a fast-cut, high-impact look -- position/size come from the Style block."""
    ass_lines = []
    for line in lines:
        for i in range(0, len(line), 2):
            chunk = line[i : i + 2]
            text = " ".join(word["text"] for word in chunk).upper()
            ass_lines.append(
                f"Dialogue: 0,{_format_ass_time(chunk[0]['start'])},"
                f"{_format_ass_time(chunk[-1]['end'])},Karaoke,,0,0,0,,{text}"
            )
    return ass_lines


def _ass_events_quote(
    lines: list[list[dict]],
    font: ImageFont.FreeTypeFont,
    space_width: float,
    available_width: float,
) -> list[str]:
    """"quote" preset: each row wrapped in curly quotation marks; the Style
    block sets Italic=1."""
    ass_lines = []
    for line in lines:
        for row in _split_line_for_width(line, font, space_width, available_width):
            plain_text = " ".join(word["text"] for word in row)
            ass_lines.append(
                f"Dialogue: 0,{_format_ass_time(row[0]['start'])},{_format_ass_time(row[-1]['end'])},"
                f"Karaoke,,0,0,0,,\u201c{plain_text}\u201d"
            )
    return ass_lines
