"""ASS subtitle serialization for the Caption Engine (Task 25 sections
19-28). Duplicates app.modules.video_composer.service's own proven
CAPTION_PRESET_CONFIG values, font paths, and `[Script Info]`/
`[V4+ Styles]`/`[Events]` template -- not imported, per this codebase's
established module-boundary convention (see app/modules/motion/renderer.py
and app/modules/audio/renderer.py's own identical "duplicate a proven
recipe across a module boundary" precedent; VideoComposerService's own ASS
building is instance-bound, job-scoped, and driven by real per-word
edge-tts timestamps this module never has -- see module docstring below).

No per-word "karaoke" animation (Task 25's own explicit "do NOT implement
complex word-by-word animation in this task") -- every preset here renders
one Dialogue event per CaptionSegment (a phrase/sentence chunk, section 26:
"MVP should support caption segment, not every individual word animated").
This means the two presets that are per-word-animated in the live-render
path ("emotional"'s highlight box, "word_highlight"'s inline recolor)
render here as plain, static segment-level text -- same visual style
(font/color/position) otherwise, just without the per-word motion, which
requires real word timestamps this module never has (no ASR, no live TTS
word-boundary stream -- see segmentation.py's own docstring).
"""

from app.modules.caption.schemas import (
    CAPTION_ASS_INVALID,
    CAPTION_STYLE_INVALID,
    CaptionError,
    CaptionSegment,
)

CAPTION_PRESETS = ("emotional", "cinematic", "word_highlight", "big_statement", "quote", "top")

# Verbatim copy of video_composer.service.CAPTION_PRESET_CONFIG (section
# 21/22: "the Template system should define caption style... only support
# fields actually required by the renderer") -- same 6 presets, same
# knobs, so a project's chosen preset looks the same whether it was burned
# in by the live per-word renderer or this pre-computed engine.
CAPTION_PRESET_CONFIG = {
    "emotional": {"font_bold": True, "italic": False, "font_scale": 1.0, "margin_v_frac": 0.11, "alignment": 2},
    "cinematic": {"font_bold": False, "italic": False, "font_scale": 0.85, "margin_v_frac": 0.08, "alignment": 2},
    "word_highlight": {"font_bold": True, "italic": False, "font_scale": 1.0, "margin_v_frac": 0.11, "alignment": 2},
    "big_statement": {"font_bold": True, "italic": False, "font_scale": 1.8, "margin_v_frac": 0.45, "alignment": 5},
    "quote": {"font_bold": False, "italic": True, "font_scale": 0.9, "margin_v_frac": 0.45, "alignment": 5},
    "top": {"font_bold": True, "italic": False, "font_scale": 0.85, "margin_v_frac": 0.09, "alignment": 8},
}
assert set(CAPTION_PRESET_CONFIG) == set(CAPTION_PRESETS)

# Section 23's own "safe margins, never flush against the bottom edge" --
# same fixed horizontal margin video_composer already uses; vertical
# margin is per-preset (margin_v_frac above), scaled by the real output
# height at render time, so it stays proportionally safe across 9:16/16:9/
# 1:1 (section 23/24/25 -- one engine, no per-aspect-ratio special case).
MARGIN_X = 40

# Bumped whenever this module's actual ASS output would differ from what
# an old cached artifact already contains (section 36/37) -- part of the
# caption_generate.py composition root's own cache fingerprint. Bumped for
# the max_chars_per_line wrap-width fix (docs/features/104-caption-wrap-width-fix.md)
# so an existing project's already-cached (and wrongly unwrapped) captions
# regenerate correctly wrapped the next time its render is retried/rebuilt,
# instead of silently reusing the old broken artifact forever.
ENGINE_VERSION = "caption-v2"


def _format_ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _wrap_balanced(text: str, max_chars_per_line: int, max_lines: int) -> str:
    """Section 27/28: a deterministic, balanced line-break -- never AI,
    never a single ragged long line when a more even split exists. Splits
    only at word boundaries (never mid-word), preferring the break point
    closest to an even division of the text across `max_lines` lines.
    Returns the text unchanged (one line) if it already fits.
    """
    if len(text) <= max_chars_per_line or max_lines <= 1:
        return text

    words = text.split()
    if len(words) <= 1:
        return text

    best_split = None
    best_imbalance = None
    running = ""
    for i in range(len(words) - 1):
        running = (running + " " + words[i]).strip() if running else words[i]
        first_line = running
        second_line = " ".join(words[i + 1 :])
        if len(first_line) > max_chars_per_line or len(second_line) > max_chars_per_line:
            continue
        imbalance = abs(len(first_line) - len(second_line))
        if best_imbalance is None or imbalance < best_imbalance:
            best_imbalance = imbalance
            best_split = i + 1

    if best_split is None:
        # No split keeps both halves under the per-line budget -- fall
        # back to the most even word-count split anyway (still balanced,
        # just may run a little long on one line rather than losing text).
        best_split = len(words) // 2 if len(words) > 1 else 1

    lines = [" ".join(words[:best_split]), " ".join(words[best_split:])]
    return r"\N".join(line for line in lines[:max_lines] if line)


def _escape_ass_text(text: str) -> str:
    # ASS treats literal `{`/`}` as override-block delimiters -- a caption
    # containing them verbatim (e.g. copy-pasted script text) must not be
    # interpreted as a style override.
    return text.replace("{", "\\{").replace("}", "\\}")


def build_ass_content(
    segments: list[CaptionSegment], width: int, height: int, font_size: int,
    preset: str = "emotional", max_lines: int = 2, max_chars: int = 42,
) -> str:
    """Pure function: the complete `.ass` file content. No I/O -- safe and
    fast to unit test directly. Raises CaptionError(CAPTION_STYLE_INVALID)
    for an unknown preset.
    """
    if preset not in CAPTION_PRESET_CONFIG:
        raise CaptionError(CAPTION_STYLE_INVALID, f"Unknown caption preset {preset!r}, must be one of {CAPTION_PRESETS}")
    config = CAPTION_PRESET_CONFIG[preset]

    scaled_font_size = max(20, int(font_size * config["font_scale"]))
    margin_v = int(height * config["margin_v_frac"])
    # Real user report: captions were rendering as one long line running off
    # the edge of the screen instead of wrapping to a second line. Root
    # cause: this used to divide by `max_lines - 1` (giving 42 // 1 == 42
    # for the default max_chars=42/max_lines=2), so max_chars_per_line came
    # out equal to the *whole chunk's* character budget -- since
    # segmentation.py already caps each chunk at max_chars, _wrap_balanced's
    # own "already fits on one line" check was then always true, and the
    # second line was never used. WrapStyle 2 (see the template below) means
    # ASS/libass does no wrapping of its own -- only the explicit \N this
    # function inserts -- so a too-long single line had nowhere else to go
    # but off the edge of PlayResX. Dividing the total budget across
    # max_lines (21 chars/line for the default 42/2) is what actually makes
    # _wrap_balanced produce a real second line.
    max_chars_per_line = max_chars if max_lines <= 1 else max(10, max_chars // max_lines)

    style_line = (
        f"Style: Karaoke,Arial,{scaled_font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        f"{1 if config['font_bold'] else 0},{1 if config['italic'] else 0},0,0,100,100,0,0,1,3,0,"
        f"{config['alignment']},{MARGIN_X},{MARGIN_X},{margin_v},1"
    )

    dialogue_lines = []
    for segment in segments:
        text = normalize_for_display(segment.text)
        if not text:
            continue  # section 31: never write a Dialogue for empty/whitespace-only text
        wrapped = _wrap_balanced(_escape_ass_text(text), max_chars_per_line, max_lines)
        if preset == "big_statement":
            wrapped = wrapped.upper()
        elif preset == "quote":
            wrapped = f"“{wrapped}”"
        dialogue_lines.append(
            f"Dialogue: 0,{_format_ass_time(segment.start)},{_format_ass_time(segment.end)},Karaoke,,0,0,0,,{wrapped}"
        )

    return (
        f"""[Script Info]
Title: Captions ({preset})
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
        + "\n".join(dialogue_lines)
        + ("\n" if dialogue_lines else "")
    )


def normalize_for_display(text: str) -> str:
    return " ".join(text.split()).strip()


def validate_ass_content(content: str) -> None:
    """Section 30/33/58's own "ASS parses successfully" check -- a real,
    if minimal, structural validation (required sections present, at
    least one syntactically well-formed Dialogue line if any Events exist)
    rather than a full libass-grade parser, matching section 58's own
    "verify Script Info/Styles/Events/Dialogue lines are valid" scope.
    """
    required_sections = ("[Script Info]", "[V4+ Styles]", "[Events]")
    for section in required_sections:
        if section not in content:
            raise CaptionError(CAPTION_ASS_INVALID, f"Generated ASS is missing the required {section} section.")

    style_lines = [line for line in content.splitlines() if line.startswith("Style:")]
    if not style_lines:
        raise CaptionError(CAPTION_ASS_INVALID, "Generated ASS has no Style definition.")

    for line in content.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line[len("Dialogue:") :].split(",", 9)
        if len(fields) < 10:
            raise CaptionError(CAPTION_ASS_INVALID, f"Malformed Dialogue line (expected 10 fields): {line[:80]!r}")
        if not fields[9].strip():
            raise CaptionError(CAPTION_ASS_INVALID, f"Dialogue line has empty text: {line[:80]!r}")
