"""Tests for Task 25 -- see docs/features/51-caption-engine.md. Pure,
in-memory tests of app.modules.caption.ass_writer -- no filesystem beyond
what a test itself chooses to write for a Unicode round-trip check.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.modules.caption.ass_writer import (
    CAPTION_PRESETS,
    _wrap_balanced,
    build_ass_content,
    validate_ass_content,
)
from app.modules.caption.schemas import CaptionError, CaptionSegment


def _segments() -> list[CaptionSegment]:
    return [
        CaptionSegment(id="b1_c1", beat_id="b1", start=0.0, end=2.0, text="This is the first caption."),
        CaptionSegment(id="b1_c2", beat_id="b1", start=2.0, end=4.0, text="This is the second caption."),
    ]


class BuildAssContentTests(unittest.TestCase):
    def test_every_preset_produces_valid_ass(self):
        for preset in CAPTION_PRESETS:
            content = build_ass_content(_segments(), 1080, 1920, 48, preset=preset)
            validate_ass_content(content)  # must not raise

    def test_unknown_preset_raises_style_invalid(self):
        with self.assertRaises(CaptionError) as ctx:
            build_ass_content(_segments(), 1080, 1920, 48, preset="does_not_exist")
        self.assertEqual(ctx.exception.code, "CAPTION_STYLE_INVALID")

    def test_contains_one_dialogue_line_per_segment(self):
        content = build_ass_content(_segments(), 1080, 1920, 48, preset="cinematic")
        dialogue_lines = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        self.assertEqual(len(dialogue_lines), 2)

    def test_big_statement_uppercases_text(self):
        content = build_ass_content(_segments(), 1080, 1920, 48, preset="big_statement")
        dialogue = next(line for line in content.splitlines() if line.startswith("Dialogue:"))
        text = dialogue.split(",", 9)[9].replace(r"\N", " ")
        self.assertEqual(text, "THIS IS THE FIRST CAPTION.")

    def test_quote_wraps_text_in_curly_quotes(self):
        content = build_ass_content(_segments(), 1080, 1920, 48, preset="quote")
        self.assertIn("“", content)
        self.assertIn("”", content)

    def test_empty_segment_list_produces_valid_ass_with_no_dialogue(self):
        content = build_ass_content([], 1080, 1920, 48, preset="emotional")
        validate_ass_content(content)
        self.assertNotIn("Dialogue:", content)

    def test_curly_braces_in_text_are_escaped(self):
        segments = [CaptionSegment(id="b1_c1", beat_id="b1", start=0.0, end=2.0, text="A {weird} caption")]
        content = build_ass_content(segments, 1080, 1920, 48, preset="cinematic")
        self.assertIn("\\{weird\\}", content)

    def test_output_includes_playres_matching_requested_dimensions(self):
        content = build_ass_content(_segments(), 1080, 1920, 48, preset="cinematic")
        self.assertIn("PlayResX: 1080", content)
        self.assertIn("PlayResY: 1920", content)

    def test_landscape_and_square_dimensions_both_produce_valid_ass(self):
        for width, height in [(1920, 1080), (1080, 1080)]:
            content = build_ass_content(_segments(), width, height, 48, preset="emotional")
            validate_ass_content(content)

    def test_a_full_length_chunk_actually_wraps_to_a_second_line(self):
        # Real user report: captions ran off the edge of the screen instead
        # of wrapping. Root cause was build_ass_content's own
        # max_chars_per_line computation (see ass_writer.py) coming out
        # equal to the whole chunk's max_chars budget for the default
        # max_lines=2, so _wrap_balanced's "already fits" check was always
        # true and \N was never inserted. A chunk at the default max_chars
        # budget (42) must produce a real second line, not a single long one.
        segments = [
            CaptionSegment(
                id="b1_c1", beat_id="b1", start=0.0, end=3.0,
                text="This caption line is long enough to need wrapping",
            )
        ]
        content = build_ass_content(segments, 1080, 1920, 48, preset="cinematic", max_lines=2, max_chars=42)
        dialogue_lines = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        self.assertEqual(len(dialogue_lines), 1)
        self.assertIn(r"\N", dialogue_lines[0])


class WrapBalancedTests(unittest.TestCase):
    def test_short_text_is_returned_unchanged(self):
        self.assertEqual(_wrap_balanced("short", 42, 2), "short")

    def test_long_text_is_split_at_a_word_boundary(self):
        text = "one two three four five six seven eight nine ten"
        wrapped = _wrap_balanced(text, 20, 2)
        self.assertIn(r"\N", wrapped)
        for line in wrapped.split(r"\N"):
            self.assertNotIn("  ", line)  # no doubled spaces from a mid-word cut

    def test_never_splits_mid_word(self):
        text = "alpha beta gamma delta epsilon zeta"
        wrapped = _wrap_balanced(text, 15, 2)
        rebuilt = " ".join(wrapped.split(r"\N"))
        self.assertEqual(rebuilt.split(), text.split())

    def test_single_word_too_long_to_split_is_returned_unchanged(self):
        self.assertEqual(_wrap_balanced("onereallylongword", 5, 2), "onereallylongword")

    def test_max_lines_one_never_wraps(self):
        text = "one two three four five six seven eight"
        self.assertEqual(_wrap_balanced(text, 10, 1), text)


class ValidateAssContentTests(unittest.TestCase):
    def test_missing_script_info_section_raises(self):
        with self.assertRaises(CaptionError) as ctx:
            validate_ass_content("[V4+ Styles]\nStyle: X\n[Events]\n")
        self.assertEqual(ctx.exception.code, "CAPTION_ASS_INVALID")

    def test_missing_style_line_raises(self):
        content = "[Script Info]\n[V4+ Styles]\n[Events]\n"
        with self.assertRaises(CaptionError) as ctx:
            validate_ass_content(content)
        self.assertEqual(ctx.exception.code, "CAPTION_ASS_INVALID")

    def test_malformed_dialogue_line_raises(self):
        content = "[Script Info]\n[V4+ Styles]\nStyle: X\n[Events]\nDialogue: 0,0,1,X\n"
        with self.assertRaises(CaptionError) as ctx:
            validate_ass_content(content)
        self.assertEqual(ctx.exception.code, "CAPTION_ASS_INVALID")

    def test_dialogue_with_empty_text_raises(self):
        content = "[Script Info]\n[V4+ Styles]\nStyle: X\n[Events]\nDialogue: 0,0:00:00.00,0:00:01.00,X,,0,0,0,,\n"
        with self.assertRaises(CaptionError) as ctx:
            validate_ass_content(content)
        self.assertEqual(ctx.exception.code, "CAPTION_ASS_INVALID")

    def test_well_formed_content_passes(self):
        content = build_ass_content(_segments(), 1080, 1920, 48, preset="emotional")
        validate_ass_content(content)  # must not raise


class UnicodeRoundTripTests(unittest.TestCase):
    def _round_trip(self, text: str) -> None:
        segments = [CaptionSegment(id="b1_c1", beat_id="b1", start=0.0, end=2.0, text=text)]
        content = build_ass_content(segments, 1080, 1920, 48, preset="emotional")
        validate_ass_content(content)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "captions.ass"
            path.write_text(content, encoding="utf-8")
            reread = path.read_text(encoding="utf-8")
        # A real \N line break may legitimately split this text across two
        # lines now that build_ass_content actually wraps -- collapse it
        # back to a single line before checking every character round-tripped.
        self.assertIn(text, reread.replace(r"\N", " "))

    def test_vietnamese_text_round_trips(self):
        self._round_trip("Xin chào, chúc một ngày tốt lành!")

    def test_spanish_text_round_trips(self):
        self._round_trip("¡Hola! ¿Cómo estás hoy, señor?")

    def test_english_text_round_trips(self):
        self._round_trip("A perfectly ordinary English sentence.")


if __name__ == "__main__":
    unittest.main()
