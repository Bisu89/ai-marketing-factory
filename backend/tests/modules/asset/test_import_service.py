"""Tests for app.modules.asset.import_service (Task 15 -- see
docs/features/41-local-asset-ingestion.md). A real, file-based (not
:memory:+StaticPool) SQLite DB is used because the cancel/background tests
exercise a genuine background thread alongside the main test thread -- see
tests/api/test_batch_render.py's own setUp comment for why StaticPool
breaks under real concurrent sessions.
"""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.asset.import_service import (
    cancel_import_job,
    create_import_job,
    get_import_job,
    rescan_library,
    start_import_job_in_background,
)
from app.modules.asset.models import Asset, AssetImportJob
from app.modules.asset import import_service as import_service_module


class _ImportServiceTestCase(unittest.TestCase):
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

        self.library_dir = self.tmp_path / "library"
        self.import_source = self.tmp_path / "import_source"
        self.import_source.mkdir()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _db(self):
        return self.TestSessionLocal()

    def _make_image(self, rel_path: str, size=(800, 800), color=(10, 20, 30)) -> Path:
        path = self.import_source / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color=color).save(path)
        return path

    def _run_sync(self, job_id: int) -> None:
        import_service_module._run_import(job_id, self.library_dir)

    def _get_job(self, job_id: int) -> AssetImportJob:
        db = self._db()
        try:
            return db.get(AssetImportJob, job_id)
        finally:
            db.close()

    def _assets(self) -> list[Asset]:
        db = self._db()
        try:
            return db.query(Asset).all()
        finally:
            db.close()


class BulkImportTests(_ImportServiceTestCase):
    def test_100_files_with_duplicates_and_invalid_produce_correct_totals(self):
        # 90 unique valid images, 7 exact-content duplicates of 7 of them
        # (different filename/folder, identical bytes), 3 corrupt files --
        # total 100, matching section 30/31's own worked example shape.
        # PNG (lossless), not JPEG -- JPEG's lossy quantization can encode
        # two merely-similar solid colors to byte-identical output, which
        # would make this fixture *accidentally* trigger real dedup instead
        # of testing "90 genuinely distinct files."
        for i in range(90):
            self._make_image(f"unique_{i}.png", color=(i % 255, 10, 20))
        for i in range(7):
            # Same pixel content as unique_{i}.png -> same SHA-256 hash.
            self._make_image(f"dupes/copy_of_{i}.png", color=(i % 255, 10, 20))
        for i in range(3):
            path = self.import_source / f"corrupt_{i}.jpg"
            path.write_bytes(b"not a real image, deliberately corrupt")

        job_id = create_import_job(folder=str(self.import_source), recursive=True)
        self._run_sync(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(job.total_files, 100)
        self.assertEqual(job.processed_files, 100)
        self.assertEqual(job.imported_count, 90)
        self.assertEqual(job.duplicate_count, 7)
        self.assertEqual(job.failed_count, 3)
        self.assertIsInstance(job.duration_seconds, float)
        self.assertEqual(len(self._assets()), 90)

    def test_failed_files_are_reported_with_path_and_reason(self):
        self._make_image("good.jpg")
        bad_path = self.import_source / "bad.jpg"
        bad_path.write_bytes(b"garbage")

        job_id = create_import_job(folder=str(self.import_source))
        self._run_sync(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.failed_count, 1)
        self.assertEqual(len(job.failed_files), 1)
        self.assertEqual(Path(job.failed_files[0]["path"]).name, "bad.jpg")
        self.assertTrue(job.failed_files[0]["reason"])

    def test_one_corrupt_file_does_not_stop_the_rest_of_the_import(self):
        self._make_image("before.png", color=(11, 22, 33))
        (self.import_source / "corrupt.jpg").write_bytes(b"garbage")
        self._make_image("after.png", color=(200, 150, 100))

        job_id = create_import_job(folder=str(self.import_source))
        self._run_sync(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(job.imported_count, 2)
        self.assertEqual(job.failed_count, 1)

    def test_unsupported_extension_in_an_explicit_file_list_is_reported_failed(self):
        good = self._make_image("good.jpg")
        unsupported = self.import_source / "notes.txt"
        unsupported.write_text("not a media file")

        job_id = create_import_job(paths=[str(good), str(unsupported)])
        self._run_sync(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.imported_count, 1)
        self.assertEqual(job.failed_count, 1)

    def test_folder_import_silently_skips_non_media_files_during_discovery(self):
        # Unlike an explicit path list (user picked this exact file), a
        # folder walk only ever considers supported extensions -- an
        # incidental .txt/.DS_Store style file in the tree isn't "failed",
        # it's simply not part of the import at all.
        self._make_image("photo.jpg")
        (self.import_source / "notes.txt").write_text("irrelevant")

        job_id = create_import_job(folder=str(self.import_source))
        job = get_import_job(job_id)
        self.assertEqual(job.total_files, 1)

    def test_creating_a_job_with_neither_paths_nor_folder_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_import_job()

    def test_creating_a_job_for_an_empty_folder_is_rejected(self):
        empty = self.import_source / "empty"
        empty.mkdir()
        with self.assertRaises(ValidationError):
            create_import_job(folder=str(empty))


class DuplicateDetectionTests(_ImportServiceTestCase):
    def test_same_content_across_two_separate_import_runs_is_deduplicated(self):
        first = self._make_image("original.jpg", color=(50, 60, 70))
        job1 = create_import_job(paths=[str(first)])
        self._run_sync(job1)
        self.assertEqual(self._get_job(job1).imported_count, 1)

        copy = self._make_image("elsewhere/renamed_copy.jpg", color=(50, 60, 70))
        job2 = create_import_job(paths=[str(copy)])
        self._run_sync(job2)

        job2_row = self._get_job(job2)
        self.assertEqual(job2_row.imported_count, 0)
        self.assertEqual(job2_row.duplicate_count, 1)
        self.assertEqual(len(self._assets()), 1)

    def test_two_duplicates_within_the_same_import_run_are_both_deduplicated(self):
        self._make_image("a/photo.jpg", color=(1, 2, 3))
        self._make_image("b/photo.jpg", color=(1, 2, 3))  # identical content, different folder
        self._make_image("c/different.jpg", color=(9, 9, 9))

        job_id = create_import_job(folder=str(self.import_source))
        self._run_sync(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.imported_count, 2)  # first photo.jpg + different.jpg
        self.assertEqual(job.duplicate_count, 1)  # second photo.jpg

    def test_same_filename_different_content_is_not_treated_as_a_duplicate(self):
        # "image.jpg" appearing in two different folders with genuinely
        # different pixel content must NOT be deduplicated by filename
        # alone (section 6's own explicit warning).
        self._make_image("folder_one/image.jpg", color=(200, 0, 0))
        self._make_image("folder_two/image.jpg", color=(0, 0, 200))

        job_id = create_import_job(folder=str(self.import_source))
        self._run_sync(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.imported_count, 2)
        self.assertEqual(job.duplicate_count, 0)


class MetadataAndTaggingTests(_ImportServiceTestCase):
    def test_imported_asset_has_hash_orientation_tags_and_status(self):
        self._make_image("couples/reunion/couple_hug_emotional.jpg", size=(1080, 1920))
        job_id = create_import_job(folder=str(self.import_source))
        self._run_sync(job_id)

        assets = self._assets()
        self.assertEqual(len(assets), 1)
        asset = assets[0]
        self.assertIsNotNone(asset.content_hash)
        self.assertEqual(asset.orientation, "PORTRAIT")
        self.assertEqual(asset.status, "ACTIVE")
        self.assertEqual(asset.source, "LOCAL_IMPORT")
        self.assertIn("couples", asset.tags)
        self.assertIn("reunion", asset.tags)
        self.assertIn("couple", asset.tags)
        self.assertIn("hug", asset.tags)
        self.assertIn("emotional", asset.tags)
        self.assertEqual(asset.category, "Couple")
        self.assertEqual(asset.emotion, "Cảm động")
        self.assertIsNotNone(asset.thumbnail_path)
        self.assertTrue(Path(asset.thumbnail_path).exists())


class CancelTests(_ImportServiceTestCase):
    def test_cancel_stops_future_work_and_keeps_already_imported_assets(self):
        for i in range(60):
            self._make_image(f"img_{i:03d}.jpg", color=(i % 255, i % 200, i % 150))

        job_id = create_import_job(folder=str(self.import_source))

        # Progress is only *committed* (so a poller in another session can
        # see it) every _PROGRESS_COMMIT_INTERVAL files -- a real 800x800
        # solid-color thumbnail is fast enough that, uncancelled, 60 of
        # them could finish before a poll even lands. A tiny artificial
        # per-file delay (only in this test) gives cancellation a real,
        # reliable window without slowing down the actual import pipeline.
        real_thumbnail = import_service_module.generate_image_thumbnail

        def _slow_thumbnail(*args, **kwargs):
            time.sleep(0.05)
            return real_thumbnail(*args, **kwargs)

        with patch.object(import_service_module, "generate_image_thumbnail", side_effect=_slow_thumbnail):
            start_import_job_in_background(job_id, self.library_dir)

            # Cancellation is checked in-memory once per file (see
            # import_service._CANCEL_EVENTS), independent of progress-commit
            # batching -- just confirm the job has actually started running,
            # then cancel right away for the widest safety margin against
            # system-load timing jitter (waiting for a whole commit batch
            # to land first was flaky under load).
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if self._get_job(job_id).status == "RUNNING":
                    break
                time.sleep(0.01)

            cancel_import_job(job_id)

            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                if self._get_job(job_id).status in ("CANCELLED", "COMPLETED"):
                    break
                time.sleep(0.05)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "CANCELLED")
        self.assertLess(job.processed_files, job.total_files)
        # Whatever was already imported before cancellation must still be
        # there, not rolled back -- section 28's own "do not roll back
        # hundreds of successful imports unnecessarily."
        self.assertEqual(len(self._assets()), job.imported_count)
        self.assertGreater(job.imported_count, 0)

    def test_cancelling_an_already_completed_job_is_a_no_op(self):
        self._make_image("only.jpg")
        job_id = create_import_job(folder=str(self.import_source))
        self._run_sync(job_id)
        self.assertEqual(self._get_job(job_id).status, "COMPLETED")

        cancel_import_job(job_id)
        self.assertEqual(self._get_job(job_id).status, "COMPLETED")


class RescanTests(_ImportServiceTestCase):
    def _import_one(self, color=(30, 40, 50)) -> Asset:
        self._make_image("photo.jpg", color=color)
        job_id = create_import_job(folder=str(self.import_source))
        self._run_sync(job_id)
        return self._assets()[0]

    def test_rescan_does_not_misclassify_a_pre_existing_audio_asset_as_invalid(self):
        # A real regression: rescan_library used to force *every*
        # non-"image" asset through extract_video_metadata (ffprobe
        # -select_streams v:0), which finds no video stream in an audio
        # file and raises -- silently flipping perfectly healthy legacy
        # audio assets (registered before Task 15, via the plain bare
        # POST /assets, never through this task's own ingestion pipeline --
        # see section 4's image/video-only scope) to INVALID on every
        # re-scan. Found via real manual verification against the live
        # dev DB, not a hypothetical.
        from app.modules.asset.schemas import AssetRegisterIn
        from app.modules.asset.service import AssetService

        narration_path = self.import_source / "narration.mp3"
        narration_path.write_bytes(b"fake mp3 bytes -- never has a video stream")

        db = self._db()
        try:
            AssetService(db).register(AssetRegisterIn(filename="narration.mp3", path=str(narration_path), type="audio"))
        finally:
            db.close()

        result = rescan_library(self.library_dir)
        self.assertEqual(result["now_invalid"], 0)
        self.assertEqual(result["now_active"], 1)

        db = self._db()
        try:
            asset = db.query(Asset).filter(Asset.type == "audio").one()
            self.assertEqual(asset.status, "ACTIVE")
        finally:
            db.close()

    def test_rescan_detects_a_newly_missing_file(self):
        asset = self._import_one()
        Path(asset.path).unlink()

        result = rescan_library(self.library_dir)
        self.assertEqual(result["now_missing"], 1)

        db = self._db()
        try:
            refreshed = db.get(Asset, asset.id)
            self.assertEqual(refreshed.status, "MISSING")
            self.assertEqual(refreshed.effective_status, "MISSING")
        finally:
            db.close()

    def test_rescan_restores_asset_when_the_file_reappears(self):
        asset = self._import_one()
        original_path = Path(asset.path)
        original_path.unlink()
        rescan_library(self.library_dir)  # -> MISSING

        Image.new("RGB", (500, 500), color=(60, 70, 80)).save(original_path)
        result = rescan_library(self.library_dir)
        self.assertEqual(result["now_active"], 1)

        db = self._db()
        try:
            refreshed = db.get(Asset, asset.id)
            self.assertEqual(refreshed.status, "ACTIVE")
            self.assertEqual(refreshed.width, 500)
        finally:
            db.close()

    def test_rescan_marks_invalid_when_a_missing_files_path_now_holds_corrupt_data(self):
        asset = self._import_one()
        original_path = Path(asset.path)
        original_path.unlink()
        rescan_library(self.library_dir)  # -> MISSING

        original_path.write_bytes(b"garbage now lives at this path")
        result = rescan_library(self.library_dir)
        self.assertEqual(result["now_invalid"], 1)

        db = self._db()
        try:
            self.assertEqual(db.get(Asset, asset.id).status, "INVALID")
        finally:
            db.close()

    def test_rescan_does_not_reprocess_already_active_assets(self):
        self._make_image("one.png", color=(11, 22, 33))
        self._make_image("two.png", color=(200, 150, 100))
        job_id = create_import_job(folder=str(self.import_source))
        self._run_sync(job_id)
        self.assertEqual(len(self._assets()), 2)

        result = rescan_library(self.library_dir)
        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["unchanged"], 2)
        self.assertEqual(result["now_active"], 0)
        self.assertEqual(result["now_missing"], 0)
        self.assertEqual(result["now_invalid"], 0)


if __name__ == "__main__":
    unittest.main()
