"""Task 15 section 44's own integration scenario -- "create a fixture
folder... run import... then run Task 14 matcher... verify relevant assets
rank above unrelated ones" -- adapted to this repo's actual state: Task 14
(VisualIntent/AssetMatcher/AssetSuggestion) does not exist anywhere in this
codebase. A full-repo search for those three names, run before any code in
this task was written, returned zero matches, and docs/features/ stops at
this session's own Task 13 (40-batch-video-creation.md) -- see
docs/features/41-local-asset-ingestion.md for the full finding.

The closest real, already-existing "matcher" is AssetService.search()'s
keyword-scoring (app/modules/asset/service.py, built in Task 20) -- the
exact function any future real matcher would also read Asset.tags/
category/emotion through, since Task 15's own instruction is "the
ingestion system must produce metadata compatible with the existing
matcher" and "do NOT create a second asset abstraction." This test proves
the real chain end to end: real local image files -> import_service's real
ingestion pipeline -> real Asset rows with real tags/category/emotion ->
that existing search() ranks relevant fixture assets above unrelated ones
for a synthetic query standing in for a "VisualIntent" (section 44's own
literal example: "woman + gift + surprise").
"""

import tempfile
import unittest
from pathlib import Path

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.asset.import_service import _run_import, create_import_job
from app.modules.asset.models import Asset, AssetImportJob
from app.modules.asset.service import AssetService


class IngestionToMatcherIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine, tables=[Asset.__table__, AssetImportJob.__table__])
        self.db = Session(bind=self.engine)

        from unittest.mock import patch

        # _run_import opens its own SessionLocal() -- patched to bind to
        # this same in-memory engine/session factory so the assets it
        # creates are visible to the AssetService(self.db) used below.
        from sqlalchemy.orm import sessionmaker

        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.patcher = patch("app.modules.asset.import_service.SessionLocal", self.TestSessionLocal)
        self.patcher.start()

        self.tmpdir = tempfile.TemporaryDirectory()
        self.fixtures_root = Path(self.tmpdir.name) / "fixtures" / "assets"
        self._build_fixture_library()

    def tearDown(self):
        self.patcher.stop()
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _write(self, relative_path: str, color: tuple[int, int, int]) -> None:
        path = self.fixtures_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (900, 1600), color=color).save(path)

    def _build_fixture_library(self) -> None:
        # Relevant to a "woman + gift + surprise" visual intent.
        self._write("family/celebration/woman_opening_gift_surprise.jpg", (255, 200, 200))
        self._write("family/celebration/family_gift_exchange.jpg", (255, 190, 190))
        self._write("emotional/woman_surprised_reaction.jpg", (250, 180, 180))
        self._write("couples/reunion/couple_hug_reunion_emotional.jpg", (240, 170, 170))
        self._write("couples/reunion/couple_holding_hands.jpg", (230, 160, 160))
        self._write("family/mother_daughter_laughing.jpg", (220, 150, 150))

        # Clearly unrelated fixtures -- no lexical overlap with the query
        # at all, must never outrank (or even appear alongside) the
        # relevant ones above.
        for i, name in enumerate(
            [
                "unrelated/mountain_landscape_sunrise.jpg",
                "unrelated/city_traffic_cars.jpg",
                "unrelated/ocean_waves_beach.jpg",
                "unrelated/forest_trail_hiking.jpg",
                "unrelated/desert_dunes_sand.jpg",
                "unrelated/office_desk_laptop.jpg",
                "unrelated/kitchen_table_food.jpg",
                "unrelated/street_market_vendor.jpg",
                "unrelated/night_sky_stars.jpg",
                "unrelated/factory_machine_industrial.jpg",
                "unrelated/bicycle_road_race.jpg",
                "unrelated/library_books_shelf.jpg",
                "unrelated/garden_flowers_spring.jpg",
                "unrelated/bridge_river_view.jpg",
                "unrelated/train_station_platform.jpg",
                "unrelated/snow_mountain_peak.jpg",
                "unrelated/airport_runway_plane.jpg",
                "unrelated/farm_field_tractor.jpg",
            ]
        ):
            self._write(name, (10 + i, 20 + i, 30 + i))

        # 24 fixtures total -- comfortably over section 44's "at least 20."
        self.total_fixture_count = 6 + 18

    def test_import_then_search_ranks_relevant_assets_above_unrelated(self):
        job_id = create_import_job(folder=str(self.fixtures_root), recursive=True)
        _run_import(job_id, Path(tempfile.mkdtemp()))  # library_dir only used for thumbnails

        job = self.db.get(AssetImportJob, job_id)
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(job.imported_count, self.total_fixture_count)
        self.assertEqual(job.failed_count, 0)

        service = AssetService(self.db)
        # The synthetic "VisualIntent" from section 44's own worked
        # example: "VisualIntent: woman + gift + surprise."
        results = service.search(query=["woman", "gift", "surprise"], asset_type="image")

        result_names = [asset.filename for asset in results]
        self.assertIn("woman_opening_gift_surprise.jpg", result_names)
        # The exact triple-match must rank at the very top -- it scores
        # highest under _score_asset's own exact-tag-match weighting.
        self.assertEqual(result_names[0], "woman_opening_gift_surprise.jpg")

        unrelated_names = {
            "mountain_landscape_sunrise.jpg", "city_traffic_cars.jpg", "ocean_waves_beach.jpg",
            "forest_trail_hiking.jpg", "desert_dunes_sand.jpg", "office_desk_laptop.jpg",
        }
        self.assertTrue(unrelated_names.isdisjoint(result_names))

    def test_import_populates_category_and_emotion_the_matcher_can_also_filter_on(self):
        job_id = create_import_job(folder=str(self.fixtures_root), recursive=True)
        _run_import(job_id, Path(tempfile.mkdtemp()))

        service = AssetService(self.db)
        gift_asset = next(
            a for a in service.search(asset_type="image") if a.filename == "woman_opening_gift_surprise.jpg"
        )
        self.assertEqual(gift_asset.category, "Family")  # from the "family" folder tag
        self.assertEqual(gift_asset.orientation, "PORTRAIT")

        couple_asset = next(
            a for a in service.search(asset_type="image") if a.filename == "couple_hug_reunion_emotional.jpg"
        )
        self.assertEqual(couple_asset.category, "Couple")
        self.assertEqual(couple_asset.emotion, "Cảm động")

        # Category/emotion filters (Task 15's own Smart Library filters)
        # work against the exact same real, ingested rows.
        family_only = service.search(asset_type="image", category="Family")
        self.assertIn("woman_opening_gift_surprise.jpg", [a.filename for a in family_only])
        self.assertNotIn("mountain_landscape_sunrise.jpg", [a.filename for a in family_only])


if __name__ == "__main__":
    unittest.main()
