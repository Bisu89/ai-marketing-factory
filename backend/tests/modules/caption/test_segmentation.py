"""Tests for Task 25 -- see docs/features/51-caption-engine.md. Pure,
in-memory tests of app.modules.caption.segmentation -- no filesystem, no
FFmpeg, no Project/Beat rows (see that module's own docstring for why: it
takes plain text + a [start, end] float window in, and returns plain
CaptionSegment objects out).
"""

import unittest

from app.modules.caption.schemas import CaptionError, CaptionSegmentationConfig, CaptionWordTiming
from app.modules.caption.segmentation import (
    _rebalance_minimum_duration,
    normalize_caption_text,
    split_beat_into_segments,
    split_text_into_chunks,
)


def _words(*specs: tuple[str, float, float]) -> list[CaptionWordTiming]:
    return [CaptionWordTiming(text=t, start=s, end=e) for t, s, e in specs]


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

    def test_no_lone_one_word_card_from_a_sentence_tail(self):
        # Real user report ("nhiều đoạn có đúng 1 chữ"): the greedy walk
        # left sentence tails like "me." / "face." on their own card.
        text = "Everyone in it was smiling. Everyone except me. It was my face."
        chunks = split_text_into_chunks(text, max_words=6, max_chars=38)
        one_word = [c for c in chunks if len(c.split()) == 1]
        self.assertEqual(one_word, [], f"orphan 1-word card(s): {one_word}")

    def test_a_whole_short_sentence_still_gets_its_own_card(self):
        # The merge only touches 1-word chunks -- a genuine short line
        # (multi-word whole sentence) is left alone.
        chunks = split_text_into_chunks("It rang again. Nobody was there.", max_words=6, max_chars=38)
        self.assertIn("Nobody was there.", chunks)

    def test_orphan_merge_never_exceeds_the_char_limit(self):
        chunks = split_text_into_chunks("alpha beta gamma delta epsilon zeta eta theta", max_words=20, max_chars=15)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 15)

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


class RealWordTimingTests(unittest.TestCase):
    """Task 62 -- see docs/features/62-caption-real-word-timing.md. A real,
    reported bug: the weighted-text-length estimate below assumes a
    uniform words-per-second pace across a whole Beat, which real speech
    (natural pauses at commas/sentence-ends) never actually keeps -- a
    caption could disappear before its own words had even started being
    spoken. These tests confirm real per-word timing (when supplied and
    matching the text's own word count) is what actually positions each
    segment, not the estimate.
    """

    def test_segment_starts_exactly_when_its_own_first_real_word_does(self):
        config = CaptionSegmentationConfig(max_words=2, max_chars=200)
        # "Vợ bước" / "vào phòng," -- two 2-word chunks (max_words=2), with
        # a real ~0.8s gap between "bước" ending and "vào" starting (a
        # natural mid-clause pause the weighted estimate has no way to
        # know about). The Beat's own official window (6.41..10.04) is
        # deliberately wider than where the real words actually sit
        # (7.41..9.20) -- Voice's own min-duration rebalancing can shift a
        # Beat's boundary a little away from its real audio content, so
        # the real (gapless-stitched) timeline is rescaled onto the Beat's
        # own window rather than assumed to line up with it exactly (see
        # _real_word_boundaries's own docstring).
        words = _words(("Vợ", 7.41, 7.65), ("bước", 7.65, 7.86), ("vào", 8.65, 8.83), ("phòng,", 8.83, 9.20))
        segments = split_beat_into_segments("b1", "Vợ bước vào phòng,", start=6.41, end=10.04, config=config, words=words)
        self.assertEqual(len(segments), 2)
        # First segment starts at the Beat's own start (not its first
        # word's real start) -- nothing to caption yet, so the on-screen
        # text simply appears as soon as the Beat itself begins.
        self.assertAlmostEqual(segments[0].start, 6.41, places=6)
        # Second segment starts well past the beat's own halfway point
        # (8.225s) -- reflecting the real ~0.8s pause between "bước" and
        # "vào" -- NOT at a naive proportional-by-word-count estimate
        # (the actual bug: the old weighted model put this around 7.5s,
        # long before the real audio even reached "vào"). Exact expected
        # value: rescaling [7.41, 9.20] (real span) onto [6.41, 10.04]
        # (Beat window) maps the real 8.65 boundary to 6.41 + (8.65-7.41)
        # * ((10.04-6.41)/(9.20-7.41)) = 8.9246...
        self.assertGreater(segments[1].start, 8.225)
        self.assertAlmostEqual(segments[1].start, 8.9246, places=3)
        # Gapless: segment 1 fills the natural pause, ending exactly where
        # segment 2's own real word begins.
        self.assertAlmostEqual(segments[0].end, segments[1].start, places=6)
        self.assertAlmostEqual(segments[1].end, 10.04, places=6)

    def test_mismatched_word_count_falls_back_to_weighted_estimate(self):
        config = CaptionSegmentationConfig(max_words=20, max_chars=200)
        # Only 2 words supplied for 4-word text -- untrustworthy, must not
        # silently misalign (same caution voice.timing._timing_from_word_
        # timestamps already applies at the whole-Beat level).
        words = _words(("Vợ", 7.41, 7.65), ("bước", 7.65, 7.86))
        with_words = split_beat_into_segments("b1", "Vợ bước vào phòng", 6.41, 10.04, config, words=words)
        without_words = split_beat_into_segments("b1", "Vợ bước vào phòng", 6.41, 10.04, config, words=None)
        self.assertEqual([(s.start, s.end) for s in with_words], [(s.start, s.end) for s in without_words])

    def test_no_words_supplied_uses_weighted_estimate_unchanged(self):
        config = CaptionSegmentationConfig(max_words=4, max_chars=30)
        text = "This is a reasonably long piece of narration text for one beat."
        with_none = split_beat_into_segments("b1", text, 10.0, 16.0, config, words=None)
        with_default = split_beat_into_segments("b1", text, 10.0, 16.0, config)
        self.assertEqual([(s.start, s.end) for s in with_none], [(s.start, s.end) for s in with_default])

    def test_last_words_real_start_past_the_beats_own_official_end_never_inverts(self):
        # Regression test for a real bug found verifying this against a
        # live project: Voice's own min-duration rebalancing can shift a
        # Beat's official `end` a few ms *before* where its own last
        # word's real audio actually starts. A naive hard clamp to `end`
        # would then produce start > end for that last segment (or a
        # near-zero sliver after the old "clamp then floor to +0.01"
        # fallback) -- the rescale approach must never do either.
        config = CaptionSegmentationConfig(max_words=2, max_chars=200)
        words = _words(("Anh", 10.050, 10.287), ("ăn", 10.287, 10.450), ("tối", 10.450, 10.725), ("chưa?", 10.725, 11.037))
        # Beat's own official end (10.0375) sits BEFORE "Anh" even starts
        # (10.050) -- exactly the real drift found on the live project.
        segments = split_beat_into_segments("b2", "Anh ăn tối chưa?", start=8.6625, end=10.0375, config=config, words=words)
        self.assertEqual(len(segments), 2)
        for seg in segments:
            self.assertLess(seg.start, seg.end)  # never inverted
            self.assertGreaterEqual(seg.duration, 0.01 - 1e-9)  # never a degenerate zero-length flash
        self.assertAlmostEqual(segments[0].start, 8.6625, places=6)
        self.assertAlmostEqual(segments[-1].end, 10.0375, places=6)

    def test_real_timing_still_respects_max_duration_sec(self):
        config = CaptionSegmentationConfig(max_words=20, max_chars=200, max_duration_sec=2.0)
        # A long silent gap before the (only) next word would otherwise
        # stretch this single-chunk segment's display far past a
        # comfortable reading window.
        words = _words(("Hi", 0.0, 0.3))
        segments = split_beat_into_segments("b1", "Hi", 0.0, 30.0, config, words=words)
        self.assertEqual(len(segments), 1)
        self.assertLessEqual(segments[0].duration, 2.0 + 1e-6)


if __name__ == "__main__":
    unittest.main()
