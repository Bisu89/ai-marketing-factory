"""Query expansion + rule-based viral score -- all local, no AI, no network."""

import unittest
from datetime import datetime, timedelta, timezone

from app.modules.discovery import scoring
from app.modules.discovery.contracts import VideoResult
from app.modules.discovery.keywords import expand_query, keywords_from_result


def _now(days_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


class QueryExpansionTests(unittest.TestCase):
    def test_original_query_is_always_first_and_deterministic(self):
        a = expand_query("beard transformation")
        b = expand_query("Beard   Transformation")
        self.assertEqual(a[0], "beard transformation")
        self.assertEqual(a, b)

    def test_beard_topic_expands_with_related_terms(self):
        out = expand_query("beard transformation")
        self.assertIn("clean shave", out)
        self.assertLessEqual(len(out), 8)

    def test_unknown_topic_returns_just_the_query(self):
        self.assertEqual(expand_query("quarterly tax planning"), ["quarterly tax planning"])

    def test_multiword_trigger_matches(self):
        out = expand_query("before after weight loss")
        self.assertGreater(len(out), 1)

    def test_keywords_from_result_uses_title_signals(self):
        kw = keywords_from_result("Man shaves huge beard and wife is shocked", ["r/videos"], None)
        self.assertTrue(kw)
        self.assertTrue(any("beard" in k or "shave" in k for k in kw))


class ViewsScoreTests(unittest.TestCase):
    def test_missing_views_returns_none(self):
        self.assertIsNone(scoring.views_score(VideoResult(platform="p", source_url="u", title="t")))

    def test_log_compression_keeps_10m_from_destroying_smaller(self):
        big = scoring.views_score(VideoResult(platform="p", source_url="u", title="t", views=10_000_000))
        small = scoring.views_score(VideoResult(platform="p", source_url="u", title="t", views=50_000))
        self.assertLessEqual(big, 100.0)
        self.assertGreater(small, big * 0.5)  # not obliterated


class EngagementScoreTests(unittest.TestCase):
    def test_uses_only_available_metrics(self):
        v = VideoResult(platform="p", source_url="u", title="t", views=1000, likes=100)  # no comments/shares
        self.assertAlmostEqual(v.engagement_rate, 0.1)
        self.assertAlmostEqual(scoring.engagement_score(v), 100.0)

    def test_no_interaction_metrics_at_all_returns_none(self):
        v = VideoResult(platform="p", source_url="u", title="t", views=1000)
        self.assertIsNone(v.engagement_rate)
        self.assertIsNone(scoring.engagement_score(v))

    def test_missing_views_returns_none(self):
        v = VideoResult(platform="p", source_url="u", title="t", likes=500, comments=20)
        self.assertIsNone(scoring.engagement_score(v))


class RecencyScoreTests(unittest.TestCase):
    def test_buckets(self):
        cfg = scoring.ScoreConfig.default()
        mk = lambda d: VideoResult(platform="p", source_url="u", title="t", published_at=_now(d))
        self.assertEqual(scoring.recency_score(mk(2), cfg), 100.0)
        self.assertEqual(scoring.recency_score(mk(20), cfg), 80.0)
        self.assertEqual(scoring.recency_score(mk(60), cfg), 55.0)
        self.assertEqual(scoring.recency_score(mk(200), cfg), 30.0)
        self.assertEqual(scoring.recency_score(mk(900), cfg), scoring.RECENCY_FLOOR)

    def test_missing_date_returns_none(self):
        self.assertIsNone(scoring.recency_score(VideoResult(platform="p", source_url="u", title="t"),
                                                scoring.ScoreConfig.default()))


class RelevanceScoreTests(unittest.TestCase):
    def test_on_topic_beats_off_topic(self):
        terms = ["beard", "transformation", "shave"]
        on = VideoResult(platform="p", source_url="u", title="Epic beard shave transformation reveal")
        off = VideoResult(platform="p", source_url="u", title="Funny cat compilation")
        self.assertGreater(scoring.relevance_score(on, terms), scoring.relevance_score(off, terms))
        self.assertLess(scoring.relevance_score(off, terms), 20.0)


class ShortFormScoreTests(unittest.TestCase):
    def test_vertical_short_scores_high_longer_not_rejected(self):
        cfg = scoring.ScoreConfig.default()
        short_vert = VideoResult(platform="p", source_url="u", title="t", duration_sec=30, width=9, height=16)
        long_land = VideoResult(platform="p", source_url="u", title="t", duration_sec=1200, width=16, height=9)
        s_short = scoring.short_form_score(short_vert, cfg)
        s_long = scoring.short_form_score(long_land, cfg)
        self.assertGreater(s_short, s_long)
        self.assertIsNotNone(s_long)  # not rejected, just lower
        self.assertGreater(s_long, 0)

    def test_no_duration_no_aspect_returns_none(self):
        self.assertIsNone(scoring.short_form_score(VideoResult(platform="p", source_url="u", title="t"),
                                                   scoring.ScoreConfig.default()))


class CompositeTests(unittest.TestCase):
    def test_weights_renormalize_over_available_components(self):
        # Reddit-shaped: no views, no engagement -> those weights drop out,
        # score still lands in 0..100 and reflects the rest.
        v = VideoResult(
            platform="reddit", source_url="u",
            title="Man shaves beard, wife does not recognize him - emotional reveal",
            likes=5000, comments=200, published_at=_now(3), duration_sec=40, width=9, height=16,
            content_tags=["r/videos"],
        )
        scoring.score_result(v, ["beard", "shave", "wife"])
        self.assertGreater(v.viral_score, 0.0)
        self.assertLessEqual(v.viral_score, 100.0)
        self.assertGreater(v.content_signal_score, 0.0)  # "shave", "wife", "reveal", "emotional"

    def test_detect_content_tags_merges_engine_tags_and_signals(self):
        v = VideoResult(platform="p", source_url="u", title="Before after transformation",
                        content_tags=["#glowup"])
        tags = scoring.detect_content_tags(v)
        self.assertIn("#glowup", tags)
        self.assertIn("before", tags)


if __name__ == "__main__":
    unittest.main()
