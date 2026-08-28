"""Tests for app/api/v1/endpoints/assets_cleanup.py -- reclaiming disk from
the per-beat `voice_factory` / `motion_engine` intermediate Assets the
Factory pipeline registers for itself. Route handler called directly as a
plain function (this codebase's convention) against a real temp-file
SQLite with just the four tables it joins.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.assets_cleanup import (
    CleanupGeneratedRequest,
    cleanup_generated_assets,
    sweep_stale_render_cache,
)
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.asset.models import Asset
from app.modules.batch.models import Batch, BatchItem
from app.modules.beat.models import Project
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _CleanupTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.engine = create_engine(
            f"sqlite:///{self.tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Project.__table__, Batch.__table__, BatchItem.__table__,
                VideoComposeJob.__table__, VideoComposeClip.__table__, Asset.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine)
        self.settings = Settings(
            library_dir=str(self.tmp_path), anthropic_api_key="fake-test-key",
            ai_provider="anthropic", openai_api_key=None,
        )

    def tearDown(self):
        self.engine.dispose()
        self.tmpdir.cleanup()

    # -- fixture helpers -------------------------------------------------

    def _job(self, status: str, completed_days_ago: float | None = None) -> int:
        db = self.Session()
        try:
            completed_at = None
            if completed_days_ago is not None:
                completed_at = _utcnow() - timedelta(days=completed_days_ago)
            job = VideoComposeJob(
                title="t", script_text="s", status=status,
                created_at=_utcnow(), completed_at=completed_at,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job.id
        finally:
            db.close()

    def _project(self, render_job_id: int | None = None) -> int:
        db = self.Session()
        try:
            n = db.query(Project).count()
            p = Project(name=f"p{n}", slug=f"p-{n}", beat_plan_json={}, render_job_id=render_job_id)
            db.add(p)
            db.commit()
            db.refresh(p)
            return p.id
        finally:
            db.close()

    def _batch_item(self, project_id: int, render_job_id: int) -> None:
        db = self.Session()
        try:
            b = Batch(name="b")
            db.add(b)
            db.commit()
            db.refresh(b)
            db.add(BatchItem(
                batch_id=b.id, index=1, script_text="s",
                project_id=project_id, render_job_id=render_job_id,
            ))
            db.commit()
        finally:
            db.close()

    def _beat_asset(self, kind: str, project_id: int, beat: str, *, content: bytes = b"x" * 2048) -> int:
        """Create a real file at the pipeline's deterministic path and an
        Asset row pointing at it. kind: 'voice' -> _voice/.../beat_*.wav
        (source voice_factory); 'motion' -> _motion/.../beat_*.mp4
        (source motion_engine); 'image' -> ai_image_generator.
        """
        sub, ext, source = {
            "voice": ("_voice", "wav", "voice_factory"),
            "motion": ("_motion", "mp4", "motion_engine"),
            "image": ("_imagegen", "png", "ai_image_generator"),
        }[kind]
        d = self.tmp_path / sub / f"project_{project_id}"
        d.mkdir(parents=True, exist_ok=True)
        fp = d / f"beat_{beat}.{ext}"
        fp.write_bytes(content)
        db = self.Session()
        try:
            a = Asset(
                filename=fp.name, path=str(fp.resolve()), type="audio" if kind == "voice" else "video",
                source=source, filesize_bytes=len(content),
            )
            db.add(a)
            db.commit()
            db.refresh(a)
            return a.id
        finally:
            db.close()

    def _run(self, **kwargs):
        db = self.Session()
        try:
            return cleanup_generated_assets(CleanupGeneratedRequest(**kwargs), db=db, settings=self.settings)
        finally:
            db.close()

    def _asset_ids(self) -> set[int]:
        db = self.Session()
        try:
            return {a.id for a in db.query(Asset).all()}
        finally:
            db.close()


class CleanupGeneratedTests(_CleanupTestCase):
    def test_completed_project_assets_are_unregistered_and_files_deleted(self):
        job = self._job("completed")
        pid = self._project(render_job_id=job)
        a1 = self._beat_asset("voice", pid, "01")
        a2 = self._beat_asset("voice", pid, "02")
        a3 = self._beat_asset("motion", pid, "01")

        result = self._run()

        self.assertEqual(result.projects_cleaned, [pid])
        self.assertEqual(result.assets_unregistered, 3)
        self.assertGreaterEqual(result.files_deleted, 3)
        self.assertGreater(result.bytes_freed, 0)
        self.assertEqual(self._asset_ids(), set())
        self.assertFalse((self.tmp_path / "_voice" / f"project_{pid}").exists())
        self.assertFalse((self.tmp_path / "_motion" / f"project_{pid}").exists())
        del a1, a2, a3

    def test_project_with_no_render_is_skipped(self):
        pid = self._project(render_job_id=None)
        self._beat_asset("voice", pid, "01")

        result = self._run()

        self.assertEqual(result.projects_cleaned, [])
        self.assertEqual(result.assets_unregistered, 0)
        self.assertEqual(result.skipped.no_completed_render, 1)
        self.assertEqual(len(self._asset_ids()), 1)

    def test_project_with_running_render_is_skipped_as_in_progress(self):
        job = self._job("rendering_beats")  # COARSE_STATUS -> RUNNING
        pid = self._project(render_job_id=job)
        self._beat_asset("voice", pid, "01")

        result = self._run()

        self.assertEqual(result.projects_cleaned, [])
        self.assertEqual(result.skipped.render_in_progress, 1)
        self.assertEqual(result.skipped.no_completed_render, 0)
        self.assertEqual(len(self._asset_ids()), 1)

    def test_dry_run_changes_nothing_but_reports_totals(self):
        job = self._job("completed")
        pid = self._project(render_job_id=job)
        self._beat_asset("voice", pid, "01")
        self._beat_asset("motion", pid, "01")

        result = self._run(dry_run=True)

        self.assertTrue(result.dry_run)
        self.assertEqual(result.assets_unregistered, 2)
        self.assertGreater(result.bytes_freed, 0)
        self.assertEqual(len(self._asset_ids()), 2)
        self.assertTrue((self.tmp_path / "_voice" / f"project_{pid}" / "beat_01.wav").exists())

    def test_delete_files_false_unregisters_only(self):
        job = self._job("completed")
        pid = self._project(render_job_id=job)
        self._beat_asset("voice", pid, "01")

        result = self._run(delete_files=False)

        self.assertEqual(result.assets_unregistered, 1)
        self.assertEqual(result.files_deleted, 0)
        self.assertEqual(result.bytes_freed, 0)
        self.assertEqual(self._asset_ids(), set())
        self.assertTrue((self.tmp_path / "_voice" / f"project_{pid}" / "beat_01.wav").exists())

    def test_ai_images_untouched_by_default_but_optable_in(self):
        job = self._job("completed")
        pid = self._project(render_job_id=job)
        img = self._beat_asset("image", pid, "01")

        default_result = self._run()
        self.assertEqual(default_result.assets_unregistered, 0)
        self.assertIn(img, self._asset_ids())

        opted = self._run(sources=["ai_image_generator"])
        self.assertEqual(opted.assets_unregistered, 1)
        self.assertEqual(opted.skipped.unparseable_path, 0)  # _imagegen path parses
        self.assertEqual(self._asset_ids(), set())
        self.assertFalse((self.tmp_path / "_imagegen" / f"project_{pid}").exists())

    def test_project_rendered_via_batch_item_is_eligible(self):
        job = self._job("completed")
        pid = self._project(render_job_id=None)
        self._batch_item(pid, job)
        self._beat_asset("voice", pid, "01")

        result = self._run()

        self.assertEqual(result.projects_cleaned, [pid])
        self.assertEqual(self._asset_ids(), set())

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._run(sources=["voice_factory", "bogus"])

    def test_older_than_days_skips_recently_finished_projects(self):
        recent = self._project(render_job_id=self._job("completed", completed_days_ago=2))
        old = self._project(render_job_id=self._job("completed", completed_days_ago=30))
        self._beat_asset("voice", recent, "01")
        self._beat_asset("voice", old, "01")

        result = self._run(older_than_days=7)

        self.assertEqual(result.projects_cleaned, [old])
        self.assertEqual(result.skipped.too_recent, 1)

    def test_completed_job_with_no_timestamp_is_treated_as_too_recent(self):
        pid = self._project(render_job_id=self._job("completed", completed_days_ago=None))
        self._beat_asset("voice", pid, "01")

        result = self._run(older_than_days=7)

        self.assertEqual(result.projects_cleaned, [])
        self.assertEqual(result.skipped.too_recent, 1)

    def test_sweep_stale_render_cache_is_noop_when_retention_disabled(self):
        pid = self._project(render_job_id=self._job("completed", completed_days_ago=30))
        self._beat_asset("voice", pid, "01")
        self.settings.render_cache_retention_days = 0

        self.assertIsNone(sweep_stale_render_cache(self.settings))
        self.assertEqual(len(self._asset_ids()), 1)

    def test_sweep_stale_render_cache_cleans_old_projects_when_enabled(self):
        old = self._project(render_job_id=self._job("completed", completed_days_ago=30))
        recent = self._project(render_job_id=self._job("completed", completed_days_ago=1))
        self._beat_asset("voice", old, "01")
        self._beat_asset("motion", recent, "01")
        self.settings.render_cache_retention_days = 7

        # sweep_stale_render_cache opens its own SessionLocal -- point it at
        # this test's engine.
        import app.api.v1.endpoints.assets_cleanup as mod
        original = mod.SessionLocal
        mod.SessionLocal = self.Session
        try:
            result = sweep_stale_render_cache(self.settings)
        finally:
            mod.SessionLocal = original

        self.assertIsNotNone(result)
        self.assertEqual(result.projects_cleaned, [old])
        self.assertEqual(len(self._asset_ids()), 1)  # the recent project's motion clip survives
        self.assertTrue((self.tmp_path / "_motion" / f"project_{recent}" / "beat_01.mp4").exists())
        self.assertFalse((self.tmp_path / "_voice" / f"project_{old}").exists())

    def test_unparseable_path_is_counted_not_crashed(self):
        job = self._job("completed")
        self._project(render_job_id=job)
        stray = self.tmp_path / "loose.wav"
        stray.write_bytes(b"x" * 100)
        db = self.Session()
        try:
            db.add(Asset(filename="loose.wav", path=str(stray.resolve()), type="audio", source="voice_factory"))
            db.commit()
        finally:
            db.close()

        result = self._run()

        self.assertEqual(result.skipped.unparseable_path, 1)
        self.assertEqual(result.assets_unregistered, 0)


if __name__ == "__main__":
    unittest.main()
