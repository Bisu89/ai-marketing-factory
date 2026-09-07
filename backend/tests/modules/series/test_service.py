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
from app.modules.series.service import (
    create_series,
    get_series,
    list_series,
    update_series,
    update_series_studio,
)


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

    def test_studio_patch_only_touches_studio_columns(self):
        s = create_series("Decisive Battles", "grizzled narrator")
        update_series_studio(
            s.id, channel_id=7, narrative_identity="grand strategy retold",
            visual_identity_json={"palette": "sepia"},
        )
        row = get_series(s.id)
        self.assertEqual(row.channel_id, 7)
        self.assertEqual(row.narrative_identity, "grand strategy retold")
        self.assertEqual(row.visual_identity_json, {"palette": "sepia"})
        # classic fields untouched
        self.assertEqual(row.name, "Decisive Battles")
        self.assertEqual(row.character_description, "grizzled narrator")

    def test_studio_patch_missing_series_raises(self):
        with self.assertRaises(NotFoundError):
            update_series_studio(999, channel_id=1)

    def test_classic_flow_series_has_studio_defaults(self):
        s = get_series(create_series("X", "").id)
        self.assertIsNone(s.channel_id)
        self.assertEqual(s.visual_identity_json, {})

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
