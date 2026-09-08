"""Service persistence + Save system + rights -> download-capability gating.

Real temp-file SQLite DB; the orchestrator is a fake (no network).
"""

import tempfile
import unittest
import unittest.mock
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import NotFoundError
from app.db.base import Base
from app.modules.discovery import service
from app.modules.discovery.contracts import (
    DOWNLOAD_ALLOWED,
    DOWNLOAD_PERMISSION_REQUIRED,
    RIGHTS_CREATIVE_COMMONS,
    RIGHTS_NOT_ALLOWED,
    RIGHTS_UNKNOWN,
    VideoResult,
)
from app.modules.discovery.models import DiscoveryResult, DiscoverySearch
from app.modules.discovery.orchestrator import EngineStatus, SearchOutput


class _FakeOrchestrator:
    def __init__(self, results):
        self._results = results

    def search(self, query, **kwargs):
        return SearchOutput(
            query=query,
            normalized_query=query.lower(),
            expanded_queries=[query.lower(), "clean shave"],
            results=self._results,
            engine_statuses=[
                EngineStatus("reddit", "ok", len(self._results), None),
                EngineStatus("tiktok", "unavailable", 0, "no API"),
            ],
            total_before_dedup=len(self._results),
        )


def _cc_youtube():
    return VideoResult(platform="youtube", source_url="https://youtube.com/watch?v=cc1",
                       title="CC beard short", rights_status=RIGHTS_CREATIVE_COMMONS,
                       attribution="\"CC beard short\" by X (CC BY 3.0)", views=100000, likes=9000,
                       published_at=datetime.now(timezone.utc), duration_sec=40, width=9, height=16)


def _unknown_reddit():
    return VideoResult(platform="reddit", source_url="https://reddit.com/r/x/1",
                       title="Some beard clip", rights_status=RIGHTS_UNKNOWN, likes=500, comments=20,
                       published_at=datetime.now(timezone.utc))


def _blocked_tiktok():
    return VideoResult(platform="tiktok", source_url="https://tiktok.com/@x/video/1",
                       title="Beard clip", rights_status=RIGHTS_NOT_ALLOWED)


class DownloadCapabilityTests(unittest.TestCase):
    def test_creative_commons_youtube_is_downloadable(self):
        self.assertEqual(service._download_capability(RIGHTS_CREATIVE_COMMONS, "youtube"), DOWNLOAD_ALLOWED)

    def test_unknown_is_permission_required(self):
        self.assertEqual(service._download_capability(RIGHTS_UNKNOWN, "reddit"), DOWNLOAD_PERMISSION_REQUIRED)
        self.assertEqual(service._download_capability(RIGHTS_UNKNOWN, "youtube"), DOWNLOAD_PERMISSION_REQUIRED)

    def test_not_allowed_is_permission_required_never_downloadable(self):
        self.assertEqual(service._download_capability(RIGHTS_NOT_ALLOWED, "youtube"), DOWNLOAD_PERMISSION_REQUIRED)


class ServicePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.tmp.name) / 'd.db'}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(
            bind=self.engine, tables=[DiscoverySearch.__table__, DiscoveryResult.__table__]
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._p = unittest.mock.patch("app.modules.discovery.service.SessionLocal", self.SessionLocal)
        self._p.start()
        service.clear_cache()

    def tearDown(self):
        self._p.stop()
        self.engine.dispose()
        self.tmp.cleanup()

    def test_run_search_persists_search_and_scored_results(self):
        orch = _FakeOrchestrator([_cc_youtube(), _unknown_reddit(), _blocked_tiktok()])
        sid = service.run_search("beard transformation", orchestrator=orch, use_cache=False)
        search, results = service.get_search(sid)
        self.assertEqual(search.query, "beard transformation")
        self.assertEqual(len(results), 3)
        caps = {r.platform: r.download_capability for r in results}
        self.assertEqual(caps["youtube"], DOWNLOAD_ALLOWED)       # CC
        self.assertEqual(caps["reddit"], DOWNLOAD_PERMISSION_REQUIRED)
        self.assertEqual(caps["tiktok"], DOWNLOAD_PERMISSION_REQUIRED)  # NOT_ALLOWED
        self.assertTrue(all(r.viral_score >= 0 for r in results))

    def test_cache_replays_same_search_id(self):
        orch = _FakeOrchestrator([_unknown_reddit()])
        a = service.run_search("beard", orchestrator=orch, use_cache=True)
        b = service.run_search("beard", orchestrator=orch, use_cache=True)
        self.assertEqual(a, b)

    def test_save_and_unsave_result(self):
        orch = _FakeOrchestrator([_unknown_reddit()])
        sid = service.run_search("beard", orchestrator=orch, use_cache=False)
        _, results = service.get_search(sid)
        rid = results[0].id

        saved = service.save_result(rid, collection="Beard", notes="great hook")
        self.assertEqual(saved.collection, "Beard")
        self.assertIsNotNone(saved.saved_at)
        self.assertEqual([r.id for r in service.list_saved()], [rid])

        service.unsave_result(rid)
        self.assertEqual(service.list_saved(), [])

    def test_save_missing_result_raises(self):
        with self.assertRaises(NotFoundError):
            service.save_result(9999, collection="Other", notes=None)

    def test_find_similar_derives_keywords_and_runs_new_search(self):
        orch = _FakeOrchestrator([
            VideoResult(platform="reddit", source_url="https://r/1",
                        title="Man shaves huge beard and wife is shocked", rights_status=RIGHTS_UNKNOWN),
        ])
        sid = service.run_search("beard", orchestrator=orch, use_cache=False)
        _, results = service.get_search(sid)
        keywords, new_sid = service.find_similar(results[0].id, orchestrator=orch)
        self.assertTrue(keywords)
        self.assertNotEqual(new_sid, sid)


if __name__ == "__main__":
    unittest.main()
