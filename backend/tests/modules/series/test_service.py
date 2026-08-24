"""Tests for the pure Series module (create/get/list/update) -- no
app.modules.beat involved, mirrors tests/modules/batch/'s own scope.
"""

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import NotFoundError
from app.db.base import Base
from app.modules.series.models import Series
from app.modules.series.service import create_series, get_series, list_series, update_series


class SeriesServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine, tables=[Series.__table__])
        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.patcher = patch("app.modules.series.service.SessionLocal", self.TestSessionLocal)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()

    def test_create_and_get_series(self):
        series = create_series("100 Days to Rebuild My Life", "male, 28, short messy hair, grey hoodie")
        fetched = get_series(series.id)
        self.assertEqual(fetched.name, "100 Days to Rebuild My Life")
        self.assertEqual(fetched.character_description, "male, 28, short messy hair, grey hoodie")

    def test_get_missing_series_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            get_series(999)

    def test_list_series_returns_newest_first(self):
        first = create_series("Series A", "")
        second = create_series("Series B", "")
        ids = [s.id for s in list_series()]
        self.assertEqual(ids, [second.id, first.id])

    def test_update_series_changes_name_and_description(self):
        series = create_series("Original Name", "original description")
        updated = update_series(series.id, "New Name", "new description")
        self.assertEqual(updated.name, "New Name")
        self.assertEqual(updated.character_description, "new description")
        refetched = get_series(series.id)
        self.assertEqual(refetched.name, "New Name")

    def test_update_missing_series_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            update_series(999, "x", "y")


if __name__ == "__main__":
    unittest.main()
