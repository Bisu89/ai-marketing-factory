"""Tests for app.modules.voice.timing (Task 22 -- see
docs/features/48-voice-factory-local-tts.md sections 14-23). Pure,
deterministic, no I/O -- no filesystem, no TTS engine, no ffmpeg.
"""

import unittest

from app.modules.voice.schemas import BeatTimingInput, VoiceError, WordTiming
from app.modules.voice.timing import compute_beat_timing


class WeightedEstimateTests(unittest.TestCase):
    def test_longer_beat_gets_a_larger_share_than_a_shorter_one(self):
        beats = [
            BeatTimingInput(beat_id="short", text="Hi there."),
            BeatTimingInput(beat_id="long", text="This is a much longer sentence with many more words in it."),
        ]
        timings = compute_beat_timing(beats, total_duration=20.0)
        by_id = {t.beat_id: t for t in timings}
        self.assertGreater(by_id["long"].duration, by_id["short"].duration)

    def test_equal_text_yields_equal_shares(self):
        beats = [
            BeatTimingInput(beat_id="a", text="Four short words here."),
            BeatTimingInput(beat_id="b", text="Four short words here."),
        ]
        timings = compute_beat_timing(beats, total_duration=10.0)
        self.assertAlmostEqual(timings[0].duration, timings[1].duration, places=6)

    def test_not_an_equal_division_when_text_lengths_differ(self):
        # Guards against a regression back to "just split total_duration
        # evenly across beats regardless of content" (section 17's own
        # explicit "not equal division" requirement).
        beats = [
            BeatTimingInput(beat_id="a", text="One."),
            BeatTimingInput(beat_id="b", text="One two three four five six seven eight nine ten."),
        ]
        timings = compute_beat_timing(beats, total_duration=22.0)
        even_share = 22.0 / 2
        self.assertNotAlmostEqual(timings[0].duration, even_share, places=3)

    def test_punctuation_adds_weight_over_plain_word_count(self):
        # Same word count, but one beat has sentence-ending/comma pauses --
        # section 18's own punctuation-pause weighting.
        beats = [
            BeatTimingInput(beat_id="plain", text="one two three four five"),
            BeatTimingInput(beat_id="punct", text="One, two, three. Four! Five?"),
        ]
        timings = compute_beat_timing(beats, total_duration=10.0)
        by_id = {t.beat_id: t for t in timings}
        self.assertGreater(by_id["punct"].duration, by_id["plain"].duration)

    def test_blank_narration_still_gets_a_real_nonzero_minimum_share(self):
        beats = [
            BeatTimingInput(beat_id="a", text=""),
            BeatTimingInput(beat_id="b", text="Some real narration text here."),
        ]
        timings = compute_beat_timing(beats, total_duration=10.0)
        self.assertGreater(timings[0].duration, 0.0)


class GaplessStitchingTests(unittest.TestCase):
    def test_first_beat_starts_at_zero_and_last_ends_at_total_duration(self):
        beats = [BeatTimingInput(beat_id=f"b{i}", text="Some words here.") for i in range(4)]
        timings = compute_beat_timing(beats, total_duration=17.3)
        self.assertEqual(timings[0].start, 0.0)
        self.assertAlmostEqual(timings[-1].end, 17.3, places=6)

    def test_every_beat_start_equals_previous_end_no_gaps_or_overlaps(self):
        beats = [BeatTimingInput(beat_id=f"b{i}", text="A beat with some words.") for i in range(5)]
        timings = compute_beat_timing(beats, total_duration=30.0)
        for prev, cur in zip(timings, timings[1:]):
            self.assertEqual(prev.end, cur.start)

    def test_single_beat_spans_the_full_duration(self):
        timings = compute_beat_timing([BeatTimingInput(beat_id="only", text="Hello.")], total_duration=5.0)
        self.assertEqual(len(timings), 1)
        self.assertEqual(timings[0].start, 0.0)
        self.assertAlmostEqual(timings[0].end, 5.0, places=6)


class MinimumDurationRebalanceTests(unittest.TestCase):
    def test_a_very_short_beat_is_clamped_up_to_the_minimum(self):
        beats = [
            BeatTimingInput(beat_id="tiny", text="Hi."),
            BeatTimingInput(beat_id="huge", text=" ".join(["word"] * 50)),
        ]
        timings = compute_beat_timing(beats, total_duration=20.0, min_beat_duration=2.0)
        by_id = {t.beat_id: t for t in timings}
        self.assertGreaterEqual(by_id["tiny"].duration, 2.0 - 1e-6)

    def test_never_deletes_a_beat_even_when_minimum_cannot_be_satisfied(self):
        beats = [BeatTimingInput(beat_id=f"b{i}", text="Hi.") for i in range(10)]
        timings = compute_beat_timing(beats, total_duration=3.0, min_beat_duration=5.0)
        self.assertEqual(len(timings), 10)
        total = sum(t.duration for t in timings)
        self.assertAlmostEqual(total, 3.0, places=6)

    def test_rebalancing_still_produces_a_gapless_contiguous_sequence(self):
        beats = [
            BeatTimingInput(beat_id="tiny1", text="Hi."),
            BeatTimingInput(beat_id="tiny2", text="Ok."),
            BeatTimingInput(beat_id="huge", text=" ".join(["word"] * 40)),
        ]
        timings = compute_beat_timing(beats, total_duration=15.0, min_beat_duration=1.5)
        self.assertEqual(timings[0].start, 0.0)
        for prev, cur in zip(timings, timings[1:]):
            self.assertEqual(prev.end, cur.start)
        self.assertAlmostEqual(timings[-1].end, 15.0, places=6)


class WordTimestampAlignmentTests(unittest.TestCase):
    def _word_timestamps(self, words: list[str], word_duration: float = 0.4) -> list[WordTiming]:
        timestamps = []
        t = 0.0
        for w in words:
            timestamps.append(WordTiming(text=w, start=t, end=t + word_duration))
            t += word_duration
        return timestamps

    def test_uses_real_word_boundaries_when_word_counts_line_up(self):
        beats = [
            BeatTimingInput(beat_id="a", text="one two"),
            BeatTimingInput(beat_id="b", text="three four five"),
        ]
        words = self._word_timestamps(["one", "two", "three", "four", "five"])
        total_duration = words[-1].end
        timings = compute_beat_timing(beats, total_duration=total_duration, word_timestamps=words)
        by_id = {t.beat_id: t for t in timings}
        self.assertAlmostEqual(by_id["a"].start, 0.0, places=6)
        self.assertAlmostEqual(by_id["a"].end, 0.8, places=6)  # end of word "two"
        self.assertAlmostEqual(by_id["b"].end, total_duration, places=6)

    def test_falls_back_to_weighted_estimate_when_word_count_drifts_too_far(self):
        beats = [BeatTimingInput(beat_id="a", text="one two three four five six seven eight nine ten")]
        # Only 2 real words reported -- drifts far past the beat's own
        # expected 10-word count, so the alignment path must not be trusted.
        words = self._word_timestamps(["one", "two"])
        timings = compute_beat_timing(beats, total_duration=10.0, word_timestamps=words)
        self.assertEqual(len(timings), 1)
        self.assertAlmostEqual(timings[0].end, 10.0, places=6)

    def test_falls_back_when_a_beat_has_no_narration_text_to_anchor_to(self):
        beats = [BeatTimingInput(beat_id="a", text=""), BeatTimingInput(beat_id="b", text="one two")]
        words = self._word_timestamps(["one", "two"])
        timings = compute_beat_timing(beats, total_duration=5.0, word_timestamps=words)
        self.assertEqual(len(timings), 2)
        self.assertEqual(timings[0].start, 0.0)
        self.assertAlmostEqual(timings[-1].end, 5.0, places=6)

    def test_real_inter_sentence_gaps_are_preserved_not_collapsed(self):
        # Real user report: captions drifted increasingly ahead of the
        # narration audio toward the middle/end of longer videos. Root
        # cause: this module used to discard the real absolute word
        # positions and re-stitch every beat back-to-back with zero gap,
        # even though Task 78's sentence-by-sentence synthesis puts a real
        # ~0.35s silent gap between every beat in the actual narration.wav.
        # Four beats, each two words, with a real 0.35s gap inserted
        # before beats b/c/d -- exactly the shape real edge_tts/SAPI5
        # output has after Task 78.
        #
        # A second real regression was found and fixed verifying this
        # against a live project: naively giving each beat's `end` back to
        # its own real last word (leaving the gap unassigned to any beat)
        # broke video/audio duration matching, since Motion clip length is
        # driven by Beat.duration and a real render's video ended up
        # several seconds shorter than its own Audio Master. The fix:
        # `start` lands exactly on each beat's own real first word (what
        # captions need), but a non-last beat's `end`/`duration` extends
        # through to the *next* beat's own real start -- absorbing the gap
        # into its own duration -- so sum(duration) still equals
        # total_duration exactly.
        gap = 0.35
        word_duration = 0.4
        beats = [
            BeatTimingInput(beat_id="a", text="one two"),
            BeatTimingInput(beat_id="b", text="three four"),
            BeatTimingInput(beat_id="c", text="five six"),
            BeatTimingInput(beat_id="d", text="seven eight"),
        ]
        words: list[WordTiming] = []
        t = 0.0
        for i, w in enumerate(["one", "two", "three", "four", "five", "six", "seven", "eight"]):
            if i in (2, 4, 6):  # first word of beats b/c/d -- a real gap precedes it
                t += gap
            words.append(WordTiming(text=w, start=t, end=t + word_duration))
            t += word_duration
        total_duration = words[-1].end

        timings = compute_beat_timing(beats, total_duration=total_duration, word_timestamps=words)
        by_id = {tm.beat_id: tm for tm in timings}

        # Each beat's start must land at its own real first-word position
        # -- not at the previous beat's end (which would silently drop the
        # gap, reproducing the reported caption drift).
        self.assertAlmostEqual(by_id["a"].start, 0.0, places=6)
        self.assertAlmostEqual(by_id["b"].start, 2 * word_duration + gap, places=6)
        self.assertAlmostEqual(by_id["c"].start, 4 * word_duration + 2 * gap, places=6)
        self.assertAlmostEqual(by_id["d"].start, 6 * word_duration + 3 * gap, places=6)
        self.assertAlmostEqual(by_id["d"].end, total_duration, places=6)

        # Each non-last beat's own end extends through to the next beat's
        # start (its clip visually holds through the gap) -- gapless by
        # construction, and the video/audio duration invariant this
        # codebase relies on everywhere else still holds exactly.
        self.assertAlmostEqual(by_id["a"].end, by_id["b"].start, places=6)
        self.assertAlmostEqual(by_id["b"].end, by_id["c"].start, places=6)
        self.assertAlmostEqual(by_id["c"].end, by_id["d"].start, places=6)
        total = sum(tm.duration for tm in timings)
        self.assertAlmostEqual(total, total_duration, places=6)


class ValidationTests(unittest.TestCase):
    def test_empty_beat_list_returns_empty_timing(self):
        self.assertEqual(compute_beat_timing([], total_duration=10.0), [])

    def test_non_positive_duration_raises_voice_timing_failed(self):
        beats = [BeatTimingInput(beat_id="a", text="Hi.")]
        with self.assertRaises(VoiceError) as ctx:
            compute_beat_timing(beats, total_duration=0.0)
        self.assertEqual(ctx.exception.code, "VOICE_TIMING_FAILED")


if __name__ == "__main__":
    unittest.main()
