"""Dedup grouping + orchestrator parallelism / failure isolation / stubs."""

import unittest
from datetime import datetime, timezone

from app.modules.discovery.contracts import EngineOutcome, VideoResult
from app.modules.discovery.dedup import deduplicate, normalize_url, title_similarity
from app.modules.discovery.engines import InstagramEngine, TikTokEngine
from app.modules.discovery.engines.base import BaseEngine
from app.modules.discovery.orchestrator import SearchOrchestrator


def _v(platform, url, title, score=0.0, **kw):
    r = VideoResult(platform=platform, source_url=url, title=title, **kw)
    r.viral_score = score
    return r


class DedupTests(unittest.TestCase):
    def test_normalize_url_strips_scheme_www_and_tracking_but_keeps_video_id(self):
        # tracking params (t, si) dropped; scheme/www normalized...
        self.assertEqual(
            normalize_url("https://www.youtube.com/watch?v=abc&t=1"),
            normalize_url("http://youtube.com/watch?v=abc&si=xyz"),
        )
        # ...but the v= id itself is NOT dropped (every watch URL would
        # otherwise collapse to one string).
        self.assertNotEqual(
            normalize_url("https://youtube.com/watch?v=abc"),
            normalize_url("https://youtube.com/watch?v=def"),
        )

    def test_same_url_different_platform_is_grouped(self):
        a = _v("reddit", "https://x.com/v/1", "A cool clip", score=50)
        b = _v("youtube", "https://www.x.com/v/1/", "Totally different title here", score=80)
        out = deduplicate([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].platform, "youtube")  # higher viral score wins
        self.assertIn("reddit", out[0].also_on)

    def test_high_title_similarity_groups_across_platforms(self):
        a = _v("tiktok", "https://tt/1", "Man shaves 10 year beard wife does not recognize him", score=60)
        b = _v("reddit", "https://r/2", "Man shaves 10-year beard and wife doesn't recognize him", score=40)
        out = deduplicate([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(sorted(out[0].also_on), ["reddit"])

    def test_unrelated_videos_are_not_merged(self):
        a = _v("youtube", "https://y/1", "Beard transformation reveal", score=70)
        b = _v("youtube", "https://y/2", "How to bake sourdough bread", score=65)
        self.assertEqual(len(deduplicate([a, b])), 2)

    def test_title_similarity_bounds(self):
        self.assertEqual(title_similarity("", "anything"), 0.0)
        self.assertAlmostEqual(title_similarity("beard shave reveal", "beard shave reveal"), 1.0)


class _FakeEngine(BaseEngine):
    def __init__(self, platform, results=None, boom=False):
        self.platform = platform
        self._results = results or []
        self._boom = boom

    def is_configured(self):
        return True

    def search(self, query, options):
        if self._boom:
            raise RuntimeError("kaboom")
        return EngineOutcome.ok(self.platform, list(self._results))


class OrchestratorTests(unittest.TestCase):
    def test_one_engine_failure_does_not_sink_search(self):
        good = _FakeEngine("reddit", [
            _v("reddit", "https://r/1", "Beard shave reaction", published_at=datetime.now(timezone.utc)),
        ])
        orch = SearchOrchestrator(engines=[good, _FakeEngine("youtube", boom=True)])
        out = orch.search("beard transformation")
        statuses = {s.platform: s.status for s in out.engine_statuses}
        self.assertEqual(statuses["reddit"], "ok")
        self.assertEqual(statuses["youtube"], "error")
        self.assertEqual(out.unique_count, 1)

    def test_tiktok_and_instagram_report_unavailable_not_error(self):
        orch = SearchOrchestrator(engines=[TikTokEngine(), InstagramEngine()])
        out = orch.search("beard transformation")
        for s in out.engine_statuses:
            self.assertEqual(s.status, "unavailable")
            self.assertTrue(s.error)  # a human-readable reason
        self.assertEqual(out.unique_count, 0)

    def test_platform_filter_limits_engines_run(self):
        orch = SearchOrchestrator(engines=[
            _FakeEngine("reddit", [_v("reddit", "https://r/1", "x")]),
            _FakeEngine("youtube", [_v("youtube", "https://y/1", "y")]),
        ])
        out = orch.search("beard", platforms=["reddit"])
        self.assertEqual([s.platform for s in out.engine_statuses], ["reddit"])

    def test_results_sorted_by_viral_score_by_default(self):
        orch = SearchOrchestrator(engines=[_FakeEngine("reddit", [
            _v("reddit", "https://r/low", "Beard clip", likes=1, comments=0,
               published_at=datetime(2019, 1, 1, tzinfo=timezone.utc)),
            _v("reddit", "https://r/hi", "Beard transformation shave reveal wife reacts",
               likes=90000, comments=5000, views=3_000_000, duration_sec=45, width=9, height=16,
               published_at=datetime.now(timezone.utc)),
        ])])
        out = orch.search("beard transformation")
        self.assertEqual(out.results[0].source_url, "https://r/hi")


if __name__ == "__main__":
    unittest.main()
