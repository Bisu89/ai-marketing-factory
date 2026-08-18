"""Tests for Task 25 -- see docs/features/51-caption-engine.md. Pure,
in-memory tests of app.modules.caption.segmentation -- no filesystem, no
FFmpeg, no Project/Beat rows (see that module's own docstring for why: it
takes plain text + a [start, end] float window in, and returns plain
CaptionSegment objects out).
"""

import unittest

from app.modules.caption.schemas import CaptionError, CaptionSegmentationConfig
from app.modules.caption.segmentation import (
    _rebalance_minimum_duration,
    normalize_caption_text,
    split_beat_into_segments,
    split_text_into_chunks,
)


class NormalizeTextTests(unittest.TestCase):
    def test_collapses_internal_whitespace_and_newlines(self):
        self.assertEqual(normalize_caption_text("Hello   \n\n  world\t!"), "Hello world !")

    def test_strips_control_characters(self):
        self.assertEqual(normalize_caption_text("Hello\x00\x07 world"), "Hello world")

    def test_strips_leading_trailing_whitespace(self):
        self.assertEqual(normalize_caption_text("   padded text   "), "padded text")

    def test_blank_text_normalizes_to_empty_string(self):
        self.assertEqual(normalize_caption_text("   \n\t  "), "")


class ChunkSplittingTests(unittest.TestCase):
    def test_short_text_is_a_single_chunk(self):
        chunks = split_text_into_chunks("A short sentence.", max_words=7, max_chars=42)
        self.assertEqual(chunks, ["A short sentence."])

    def test_splits_at_sentence_boundary(self):
        chunks = split_text_into_chunks("First sentence here. Second sentence follows.", max_words=20, max_chars=200)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].rstrip().endswith("."))

    def test_splits_at_comma_when_chunk_already_non_trivial(self):
        chunks = split_text_into_chunks("Well, after a long day, we finally went home", max_words=20, max_chars=200)
        self.assertGreaterEqual(len(chunks), 2)

    def test_never_splits_after_a_single_word_at_punctuation(self):
        # "Well," alone is too trivial (len < 2) to close a chunk on its own.
        chunks = split_text_into_chunks("Well, that is that.", max_words=20, max_chars=200)
        self.assertNotEqual(chunks[0], "Well,")

    def test_hard_word_limit_splits_even_without_punctuation(self):
        text = " ".join(f"word{i}" for i in range(1, 21))  # 20 words, no punctuation at all
        chunks = split_text_into_chunks(text, max_words=5, max_chars=200)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.split()), 5)
        self.assertEqual(" ".join(chunks), text)  # every word preserved, none dropped or duplicated

    def test_hard_char_limit_splits_a_single_very_long_word_free_phrase(self):
        text = "alpha beta gamma delta epsilon zeta eta theta"
        chunks = split_text_into_chunks(text, max_words=20, max_chars=15)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 15)

    def test_never_splits_mid_word(self):
        text = "supercalifragilisticexpialidocious is one very long single word indeed"
        chunks = split_text_into_chunks(text, max_words=3, max_chars=10)
        rebuilt_words = " ".join(chunks).split()
        self.assertEqual(rebuilt_words, text.split())

    def test_question_and_exclamation_marks_are_sentence_ends(self):
        chunks = split_text_into_chunks("Are you ready? Yes I am! Let's go now.", max_words=20, max_chars=200)
        self.assertEqual(len(chunks), 3)

    def test_empty_text_yields_no_chunks(self):
        self.assertEqual(split_text_into_chunks("", max_words=7, max_chars=42), [])


class RebalanceMinimumDurationTests(unittest.TestCase):
    def test_no_rebalance_needed_when_all_already_above_minimum(self):
        result = _rebalance_minimum_duration([2.0, 2.0, 2.0], total_duration=6.0, min_duration=1.0)
        self.assertEqual(result, [2.0, 2.0, 2.0])

    def test_below_minimum_segment_is_raised_to_minimum(self):
        result = _rebalance_minimum_duration([0.2, 3.8], total_duration=4.0, min_duration=1.0)
        self.assertAlmostEqual(result[0], 1.0)
        self.assertAlmostEqual(sum(result), 4.0, places=6)

    def test_falls_back_to_even_split_when_minimum_times_n_exceeds_total(self):
        result = _rebalance_minimum_duration([0.5, 0.5, 0.5], total_duration=1.5, min_duration=1.0)
        self.assertEqual(result, [0.5, 0.5, 0.5])

    def test_empty_input_returns_empty(self):
        self.assertEqual(_rebalance_minimum_duration([], total_duration=0.0, min_duration=1.0), [])


class SplitBeatIntoSegmentsTests(unittest.TestCase):
    def test_blank_text_returns_no_segments(self):
        config = CaptionSegmentationConfig()
        self.assertEqual(split_beat_into_segments("b1", "   ", 0.0, 5.0, config), [])

    def test_non_positive_window_raises_timing_invalid(self):
        config = CaptionSegmentationConfig()
        with self.assertRaises(CaptionError) as ctx:
            split_beat_into_segments("b1", "Some text.", 5.0, 5.0, config)
        self.assertEqual(ctx.exception.code, "CAPTION_TIMING_INVALID")

    def test_reversed_window_raises_timing_invalid(self):
        config = CaptionSegmentationConfig()
        with self.assertRaises(CaptionError) as ctx:
            split_beat_into_segments("b1", "Some text.", 5.0, 2.0, config)
        self.assertEqual(ctx.exception.code, "CAPTION_TIMING_INVALID")

    def test_segments_stay_inside_the_beat_window(self):
        config = CaptionSegmentationConfig(max_words=4, max_chars=30)
        segments = split_beat_into_segments(
            "b1", "This is a reasonably long piece of narration text for one beat.", 10.0, 16.0, config
        )
        self.assertGreater(len(segments), 0)
        for seg in segments:
            self.assertGreaterEqual(seg.start, 10.0 - 1e-9)
            self.assertLessEqual(seg.end, 16.0 + 1e-9)

    def test_segments_are_contiguous_within_the_beat(self):
        config = CaptionSegmentationConfig(max_words=4, max_chars=30)
        segments = split_beat_into_segments(
            "b1", "First sentence here. Second sentence follows after it.", 0.0, 8.0, config
        )
        for prev, cur in zip(segments, segments[1:]):
            self.assertAlmostEqual(prev.end, cur.start, places=6)

    def test_no_segment_shorter_than_min_duration_unless_beat_too_short_to_allow_it(self):
        config = CaptionSegmentationConfig(max_words=3, max_chars=30, min_duration_sec=1.0)
        segments = split_beat_into_segments("b1", "One two three four five six seven eight nine.", 0.0, 20.0, config)
        for seg in segments:
            self.assertGreaterEqual(seg.duration, 1.0 - 1e-6)

    def test_segment_duration_never_exceeds_max_duration_sec(self):
        # A single short chunk given a huge beat window would otherwise
        # inherit the whole window -- section 10's own capping behavior.
        config = CaptionSegmentationConfig(max_words=20, max_chars=200, max_duration_sec=2.0)
        segments = split_beat_into_segments("b1", "Just a few words.", 0.0, 30.0, config)
        self.assertEqual(len(segments), 1)
        self.assertLessEqual(segments[0].duration, 2.0 + 1e-6)
        self.assertLess(segments[0].end, 30.0)  # capped, not stretched to fill the beat -- a trailing gap is fine

    def test_ids_are_stable_and_unique_per_beat(self):
        config = CaptionSegmentationConfig(max_words=3, max_chars=30)
        segments = split_beat_into_segments("beatX", "One two three four five six seven eight nine.", 0.0, 9.0, config)
        ids = [s.id for s in segments]
        self.assertEqual(len(ids), len(set(ids)))
        for seg_id in ids:
            self.assertTrue(seg_id.startswith("beatX_c"))

    def test_multi_sentence_narration_produces_multiple_ordered_segments(self):
        config = CaptionSegmentationConfig(max_words=6, max_chars=42)
        text = "This is the first sentence. This is the second sentence. And a third one too."
        segments = split_beat_into_segments("b1", text, 0.0, 12.0, config)
        self.assertGreaterEqual(len(segments), 3)
        starts = [s.start for s in segments]
        self.assertEqual(starts, sorted(starts))


if __name__ == "__main__":
    unittest.main()
