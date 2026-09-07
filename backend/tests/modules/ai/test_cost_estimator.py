"""Tests for app.modules.ai.cost_estimator (AI Storytelling Studio plan,
Phase 0). Pure -- production shape in, CostEstimate out.
"""

import unittest

from app.modules.ai.cost_estimator import CostEstimateInput, LlmWorkItem, estimate_story
from app.modules.ai.image_client import IMAGE_COST_USD


def _base(**kw) -> CostEstimateInput:
    d = dict(
        provider="anthropic",
        llm_work=[LlmWorkItem("story_development", 4, 2000, 1500), LlmWorkItem("scene_breakdown", 6, 1500, 3000)],
        llm_work_per_language=[LlmWorkItem("localize_scenes", 6, 2000, 2500)],
        image_count=35,
        ai_video_count=0,
        ai_video_total_seconds=0.0,
        video_provider="null",
        tts_provider="edge_tts",
        tts_word_count=2200,
        package_ai_metadata=True,
        target_language_count=1,
    )
    d.update(kw)
    return CostEstimateInput(**d)


class CostEstimateTests(unittest.TestCase):
    def test_render_is_always_zero(self):
        self.assertEqual(estimate_story(_base()).render_usd, 0.0)

    def test_image_cost_is_count_times_unit(self):
        est = estimate_story(_base(image_count=50))
        self.assertAlmostEqual(est.image_usd, round(50 * IMAGE_COST_USD, 6))

    def test_free_tts_is_zero(self):
        self.assertEqual(estimate_story(_base(tts_provider="edge_tts")).tts_usd, 0.0)
        self.assertEqual(estimate_story(_base(tts_provider="local")).tts_usd, 0.0)

    def test_null_video_provider_prices_video_at_zero_not_none(self):
        # NullVideoProvider generates nothing -- a real, confirmed $0.
        est = estimate_story(_base(video_provider="null", ai_video_count=5, ai_video_total_seconds=40))
        self.assertEqual(est.video_usd, 0.0)
        self.assertIsNotNone(est.total_usd)

    def test_unpriced_video_provider_reports_none_and_blocks_total(self):
        est = estimate_story(_base(video_provider="kling", ai_video_count=5, ai_video_total_seconds=40))
        self.assertIsNone(est.video_usd)
        self.assertIsNone(est.total_usd)
        self.assertTrue(any("video" in n.lower() for n in est.notes))

    def test_extra_languages_only_add_translate_plus_tts_not_images(self):
        one = estimate_story(_base(target_language_count=1))
        three = estimate_story(_base(target_language_count=3))
        # images are generated once, shared -- identical across language counts
        self.assertEqual(one.image_usd, three.image_usd)
        # total grows by exactly 2 * per_extra_language_usd
        self.assertAlmostEqual(three.total_usd, round(one.total_usd + 2 * one.per_extra_language_usd, 6))
        # and the marginal language is cheaper than the master (no images/research)
        self.assertLess(one.per_extra_language_usd, one.master_usd)

    def test_unconfirmed_llm_prices_flagged(self):
        est = estimate_story(_base())
        # pricing.py's claude-sonnet-5 / gpt-5.6-luna entries are estimates
        self.assertFalse(est.all_prices_confirmed)
        self.assertTrue(any("ước tính" in n for n in est.notes))

    def test_notes_are_deduped(self):
        est = estimate_story(_base())
        self.assertEqual(len(est.notes), len(set(est.notes)))

    def test_deterministic(self):
        a = estimate_story(_base())
        b = estimate_story(_base())
        self.assertEqual(a.breakdown, b.breakdown)
        self.assertEqual(a.master_usd, b.master_usd)


if __name__ == "__main__":
    unittest.main()
