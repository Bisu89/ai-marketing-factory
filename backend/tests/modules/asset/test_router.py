"""Tests for the one piece of real logic in app/modules/asset/router.py:
GET /assets/{id}/file -- a generic "give me the bytes to preview" route,
originally built for image previews (Task 32) and, since Task 36, also
used for audio previews (narration/music asset pickers) -- not type-
restricted, unlike app.modules.beat's motion-render path (get_image()),
where only an image can actually be rendered. The other routes are thin
wrappers over already-tested AssetService methods. Route handlers are
called directly as plain functions, matching this codebase's established
test convention (no TestClient anywhere in this suite).
"""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.exceptions import FileOperationError, NotFoundError
from app.db.base import Base
from app.modules.asset.import_service import get_import_job
from app.modules.asset.models import Asset, AssetImportJob
from app.modules.asset.router import (
    cancel_asset_import_job,
    get_asset_file,
    get_asset_import_job,
    get_asset_thumbnail,
    import_assets,
    rescan_assets,
    search_assets,
)
from app.modules.asset.schemas import AssetImportRequest, AssetRegisterIn
from app.modules.asset.service import AssetService


class GetAssetFileTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine, tables=[Asset.__table__])
        self.db = Session(bind=self.engine)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service = AssetService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _register_image(self, name: str = "photo.jpg") -> Asset:
        file_path = self.tmp_path / name
        file_path.write_bytes(b"fake-jpeg-bytes")
        return self.service.register(AssetRegisterIn(filename=name, path=str(file_path), type="image"))

    def test_existing_image_asset_returns_a_file_response(self):
        asset = self._register_image()
        response = get_asset_file(asset.id, self.service)
        self.assertIsInstance(response, FileResponse)
        self.assertEqual(Path(response.path), Path(asset.path))

    def test_missing_asset_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            get_asset_file(999, self.service)

    def test_non_image_asset_is_served_too(self):
        # Audio (and any other registered type) must be previewable, not
        # just images -- see docs/features/36-audio-pipeline.md's
        # narration/music asset pickers.
        file_path = self.tmp_path / "voice.mp3"
        file_path.write_bytes(b"fake-mp3-bytes")
        asset = self.service.register(AssetRegisterIn(filename="voice.mp3", path=str(file_path), type="audio"))
        response = get_asset_file(asset.id, self.service)
        self.assertIsInstance(response, FileResponse)
        self.assertEqual(Path(response.path), Path(asset.path))

    def test_asset_row_exists_but_file_deleted_from_disk_raises_file_operation_error(self):
        asset = self._register_image()
        Path(asset.path).unlink()
        with self.assertRaises(FileOperationError):
            get_asset_file(asset.id, self.service)


class ThumbnailAndFilterTests(unittest.TestCase):
    """Task 15 (see docs/features/41-local-asset-ingestion.md): thumbnail
    serving and the new Smart Library filter params on search_assets --
    exercised directly against real Asset rows with the new columns set,
    same in-memory-DB/plain-function-call convention as GetAssetFileTests.
    """

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine, tables=[Asset.__table__])
        self.db = Session(bind=self.engine)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service = AssetService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _register(self, name: str, **overrides) -> Asset:
        path = self.tmp_path / name
        path.write_bytes(b"fake-bytes")
        asset = self.service.register(AssetRegisterIn(filename=name, path=str(path), type="image"))
        for key, value in overrides.items():
            setattr(asset, key, value)
        self.db.commit()
        return asset

    def test_get_asset_thumbnail_serves_the_generated_file(self):
        thumb_path = self.tmp_path / "thumb.jpg"
        thumb_path.write_bytes(b"fake-thumbnail-bytes")
        asset = self._register("photo.jpg", thumbnail_path=str(thumb_path))

        response = get_asset_thumbnail(asset.id, self.service)
        self.assertIsInstance(response, FileResponse)
        self.assertEqual(Path(response.path), thumb_path)

    def test_get_asset_thumbnail_without_one_raises_file_operation_error(self):
        asset = self._register("photo.jpg")  # never had a thumbnail generated
        with self.assertRaises(FileOperationError):
            get_asset_thumbnail(asset.id, self.service)

    def test_search_filters_by_orientation(self):
        self._register("portrait.jpg", orientation="PORTRAIT")
        self._register("landscape.jpg", orientation="LANDSCAPE")
        results = search_assets(orientation="PORTRAIT", service=self.service)
        self.assertEqual([a.filename for a in results], ["portrait.jpg"])

    def test_search_filters_by_category_and_emotion(self):
        self._register("a.jpg", category="Couple", emotion="Vui")
        self._register("b.jpg", category="Family", emotion="Buồn")
        self.assertEqual([a.filename for a in search_assets(category="Couple", service=self.service)], ["a.jpg"])
        self.assertEqual([a.filename for a in search_assets(emotion="Buồn", service=self.service)], ["b.jpg"])

    def test_search_missing_only_excludes_assets_whose_file_still_exists(self):
        present = self._register("present.jpg")
        gone = self._register("gone.jpg")
        Path(gone.path).unlink()

        results = search_assets(missing_only=True, service=self.service)
        self.assertEqual([a.id for a in results], [gone.id])
        self.assertNotIn(present.id, [a.id for a in results])


class ImportRouterTestCase(unittest.TestCase):
    """Import/cancel/rescan router endpoints spawn a real background thread
    (see import_service.start_import_job_in_background), so this needs a
    real file-based SQLite DB, not :memory:+StaticPool -- see
    tests/api/test_batch_render.py's own setUp comment for why.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.db_path = self.tmp_path / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(bind=self.engine, tables=[Asset.__table__, AssetImportJob.__table__])
        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.patcher = patch("app.modules.asset.import_service.SessionLocal", self.TestSessionLocal)
        self.patcher.start()

        self.settings = Settings(library_dir=str(self.tmp_path / "library"))
        self.import_source = self.tmp_path / "import_source"
        self.import_source.mkdir()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _make_image(self, name: str, color=(10, 20, 30)) -> Path:
        path = self.import_source / name
        Image.new("RGB", (600, 600), color=color).save(path)
        return path

    def _wait_for_terminal(self, job_id: int, timeout: float = 10.0) -> AssetImportJob:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = get_import_job(job_id)
            if job.status in ("COMPLETED", "CANCELLED", "FAILED"):
                return job
            time.sleep(0.02)
        self.fail("import job never reached a terminal status")


class ImportEndpointTests(ImportRouterTestCase):
    def test_import_folder_via_router_completes_and_is_pollable(self):
        self._make_image("a.jpg", color=(1, 2, 3))
        self._make_image("b.jpg", color=(4, 5, 6))

        job_out = import_assets(AssetImportRequest(folder=str(self.import_source)), self.settings)
        self.assertIn(job_out.status, ("QUEUED", "RUNNING"))
        self.assertEqual(job_out.total_files, 2)

        job = self._wait_for_terminal(job_out.id)
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(job.imported_count, 2)

        polled = get_asset_import_job(job_out.id)
        self.assertEqual(polled.status, "COMPLETED")

    def test_cancel_endpoint_stops_a_running_import(self):
        for i in range(60):
            self._make_image(f"img_{i:03d}.jpg", color=(i % 255, i % 200, i % 150))

        from app.modules.asset import import_service as import_service_module

        real_thumbnail = import_service_module.generate_image_thumbnail

        def _slow_thumbnail(*args, **kwargs):
            time.sleep(0.05)
            return real_thumbnail(*args, **kwargs)

        with patch.object(import_service_module, "generate_image_thumbnail", side_effect=_slow_thumbnail):
            job_out = import_assets(AssetImportRequest(folder=str(self.import_source)), self.settings)

            # Cancellation itself is checked in-memory once per file (see
            # import_service._CANCEL_EVENTS), independent of the progress-
            # commit batching -- no need to wait for a whole batch to land,
            # just confirm the job has actually started running, then
            # cancel right away for the widest possible safety margin
            # against system-load timing jitter.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if get_import_job(job_out.id).status == "RUNNING":
                    break
                time.sleep(0.01)

            cancel_asset_import_job(job_out.id)

            job = self._wait_for_terminal(job_out.id)
            self.assertEqual(job.status, "CANCELLED")
            self.assertLess(job.processed_files, job.total_files)


class RescanEndpointTests(ImportRouterTestCase):
    def test_rescan_endpoint_reports_missing_assets(self):
        self._make_image("photo.jpg")
        job_out = import_assets(AssetImportRequest(folder=str(self.import_source)), self.settings)
        self._wait_for_terminal(job_out.id)

        db = self.TestSessionLocal()
        try:
            asset = db.query(Asset).first()
            Path(asset.path).unlink()
        finally:
            db.close()

        result = rescan_assets(self.settings)
        self.assertEqual(result.now_missing, 1)


if __name__ == "__main__":
    unittest.main()
