"""Tests for Task 27 -- see docs/features/53-thumbnail-metadata-package.md.
Pure, in-memory tests of app.modules.thumbnail.scoring -- no filesystem, no
FFmpeg, no Pillow raster I/O (see that module's own docstring: it operates
entirely on already-computed FrameStats).
"""

import unittest

from app.modules.thumbnail.schemas import FrameStats
from app.modules.thumbnail.scoring import (
    is_rejectable,
    score_frame,
    select_best_frame,
    select_best_frame_with_fallback,
)


def _stats(offset=0.5, brightness=128.0, contrast=40.0, edge_density=20.0, path="x.jpg"):
    return FrameStats(offset_fraction=offset, path=path, brightness=brightness, contrast=contrast, edge_density=edge_density)


class RejectionTests(unittest.TestCase):
    def test_near_black_frame_is_rejected(self):
        self.assertTrue(is_rejectable(_stats(brightness=5.0)))

    def test_near_white_frame_is_rejected(self):
        self.assertTrue(is_rejectable(_stats(brightness=250.0)))

    def test_flat_low_contrast_frame_is_rejected(self):
        self.assertTrue(is_rejectable(_stats(contrast=2.0)))

    def test_low_edge_density_frame_is_rejected(self):
        self.assertTrue(is_rejectable(_stats(edge_density=0.5)))

    def test_well_formed_frame_is_not_rejected(self):
        self.assertFalse(is_rejectable(_stats(brightness=128.0, contrast=40.0, edge_density=20.0)))

    def test_boundary_brightness_values_are_accepted(self):
        self.assertFalse(is_rejectable(_stats(brightness=15.0, contrast=40.0, edge_density=20.0)))
        self.assertFalse(is_rejectable(_stats(brightness=240.0, contrast=40.0, edge_density=20.0)))


class ScoringTests(unittest.TestCase):
    def test_ideal_frame_scores_higher_than_a_dim_flat_frame(self):
        ideal = _stats(brightness=128.0, contrast=60.0, edge_density=35.0)
        poor = _stats(brightness=40.0, contrast=10.0, edge_density=5.0)
        self.assertGreater(score_frame(ideal), score_frame(poor))

    def test_score_is_deterministic(self):
        stats = _stats(brightness=140.0, contrast=50.0, edge_density=25.0)
        self.assertEqual(score_frame(stats), score_frame(stats))

    def test_higher_contrast_and_edge_density_score_higher_at_same_brightness(self):
        sharper = _stats(brightness=128.0, contrast=70.0, edge_density=35.0)
        duller = _stats(brightness=128.0, contrast=20.0, edge_density=10.0)
        self.assertGreater(score_frame(sharper), score_frame(duller))

    def test_brightness_far_from_ideal_lowers_score(self):
        ideal_brightness = _stats(brightness=128.0, contrast=40.0, edge_density=20.0)
        dim_brightness = _stats(brightness=60.0, contrast=40.0, edge_density=20.0)
        self.assertGreater(score_frame(ideal_brightness), score_frame(dim_brightness))


class SelectBestFrameTests(unittest.TestCase):
    def test_empty_candidate_list_returns_none(self):
        self.assertIsNone(select_best_frame([]))

    def test_all_rejected_candidates_returns_none(self):
        candidates = [_stats(brightness=2.0), _stats(brightness=253.0), _stats(contrast=1.0)]
        self.assertIsNone(select_best_frame(candidates))

    def test_picks_the_highest_scoring_survivor(self):
        weak = _stats(offset=0.1, brightness=100.0, contrast=15.0, edge_density=8.0, path="weak.jpg")
        strong = _stats(offset=0.5, brightness=128.0, contrast=60.0, edge_density=35.0, path="strong.jpg")
        rejected = _stats(offset=0.9, brightness=250.0, contrast=60.0, edge_density=35.0, path="rejected.jpg")
        result = select_best_frame([weak, strong, rejected])
        self.assertEqual(result.path, "strong.jpg")

    def test_ties_are_broken_by_earliest_offset_deterministically(self):
        a = _stats(offset=0.7, brightness=128.0, contrast=40.0, edge_density=20.0, path="a.jpg")
        b = _stats(offset=0.2, brightness=128.0, contrast=40.0, edge_density=20.0, path="b.jpg")
        result1 = select_best_frame([a, b])
        result2 = select_best_frame([b, a])
        self.assertEqual(result1.path, "b.jpg")
        self.assertEqual(result2.path, "b.jpg")

    def test_selection_is_deterministic_across_repeated_calls(self):
        candidates = [
            _stats(offset=0.1, brightness=90.0, contrast=30.0, edge_density=15.0, path="a.jpg"),
            _stats(offset=0.4, brightness=128.0, contrast=55.0, edge_density=30.0, path="b.jpg"),
            _stats(offset=0.8, brightness=180.0, contrast=45.0, edge_density=22.0, path="c.jpg"),
        ]
        first = select_best_frame(candidates)
        second = select_best_frame(list(candidates))
        self.assertEqual(first.path, second.path)


class SelectBestFrameWithFallbackTests(unittest.TestCase):
    def test_prefers_a_real_survivor_over_falling_back(self):
        good = _stats(offset=0.5, brightness=128.0, contrast=40.0, edge_density=20.0, path="good.jpg")
        rejected = _stats(offset=0.1, brightness=2.0, contrast=40.0, edge_density=20.0, path="rejected.jpg")
        result = select_best_frame_with_fallback([good, rejected])
        self.assertEqual(result.path, "good.jpg")

    def test_falls_back_to_least_bad_when_everything_is_rejected(self):
        very_dark = _stats(offset=0.1, brightness=1.0, contrast=1.0, edge_density=0.1, path="very_dark.jpg")
        less_dark = _stats(offset=0.5, brightness=8.0, contrast=5.0, edge_density=1.5, path="less_dark.jpg")
        result = select_best_frame_with_fallback([very_dark, less_dark])
        self.assertEqual(result.path, "less_dark.jpg")

    def test_empty_candidate_list_still_returns_none(self):
        self.assertIsNone(select_best_frame_with_fallback([]))

    def test_fallback_is_deterministic(self):
        candidates = [
            _stats(offset=0.1, brightness=2.0, contrast=1.0, edge_density=0.1, path="a.jpg"),
            _stats(offset=0.5, brightness=3.0, contrast=1.5, edge_density=0.2, path="b.jpg"),
        ]
        first = select_best_frame_with_fallback(list(candidates))
        second = select_best_frame_with_fallback(list(candidates))
        self.assertEqual(first.path, second.path)


if __name__ == "__main__":
    unittest.main()
