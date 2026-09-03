"""Service tests for app.modules.news.service against a real temp-file
SQLite DB (same pattern as tests/api/test_batch_render.py). fetch_feed is
patched so no network is touched.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.news import service
from app.modules.news.feeds import FeedFetchError, FetchedEntry
from app.modules.news.models import NewsItem, NewsSource


def _entry(title: str, guid: str) -> FetchedEntry:
    return FetchedEntry(guid=guid, title=title, summary=f"summary of {title}", link=f"https://x/{guid}",
                        image_url=None, published_at=None)


class NewsServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(bind=self.engine, tables=[NewsSource.__table__, NewsItem.__table__])
        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.patcher = patch("app.modules.news.service.SessionLocal", self.TestSessionLocal)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _source(self, name="VnExpress", url="https://vnexpress.net/rss/tin-moi-nhat.rss"):
        return service.create_source(name=name, feed_url=url, category="Tổng hợp", language="vi", enabled=True)

    def test_create_source_rejects_duplicate_feed_url(self):
        self._source()
        with self.assertRaises(ValidationError):
            self._source(name="Dup")

    def test_fetch_inserts_new_items_and_dedupes_by_guid(self):
        source = self._source()
        entries = [_entry("Story A", "g1"), _entry("Story B", "g2")]
        with patch("app.modules.news.service.fetch_feed", return_value=entries):
            first = service.fetch_source(source.id)
        self.assertEqual(first.new_items, 2)

        # Second fetch: same guids -> all duplicates, nothing inserted.
        with patch("app.modules.news.service.fetch_feed", return_value=entries):
            second = service.fetch_source(source.id)
        self.assertEqual(second.new_items, 0)
        self.assertEqual(second.duplicates, 2)

        items, total = service.list_items()
        self.assertEqual(total, 2)

    def test_fetch_dedupes_same_headline_across_sources(self):
        s1 = self._source(name="A", url="https://a/rss")
        s2 = self._source(name="B", url="https://b/rss")
        with patch("app.modules.news.service.fetch_feed", return_value=[_entry("Shared wire story", "a-1")]):
            service.fetch_source(s1.id)
        # Different guid, different source, SAME title -> fingerprint dedupe.
        with patch("app.modules.news.service.fetch_feed", return_value=[_entry("shared wire story", "b-1")]):
            result = service.fetch_source(s2.id)
        self.assertEqual(result.new_items, 0)
        self.assertEqual(result.duplicates, 1)

    def test_fetch_records_feed_error_without_raising(self):
        source = self._source()
        with patch("app.modules.news.service.fetch_feed", side_effect=FeedFetchError("boom")):
            result = service.fetch_source(source.id)
        self.assertEqual(result.error, "boom")
        self.assertEqual(service.get_source(source.id).last_error, "boom")

    def test_pending_counts_only_active_statuses(self):
        source = self._source()
        with patch("app.modules.news.service.fetch_feed", return_value=[_entry("A", "g1"), _entry("B", "g2")]):
            service.fetch_source(source.id)
        items, _ = service.list_items()
        service.set_item_fields(items[0].id, status="dismissed")
        self.assertEqual(service.pending_counts_by_source().get(source.id), 1)
