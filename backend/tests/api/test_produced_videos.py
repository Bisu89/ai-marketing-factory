"""Tests for app/api/v1/endpoints/produced_videos.py -- the read-only browse of
every finished render. A real file-backed SQLite shared across
Project/VideoComposeJob; VideoComposeJob rows are inserted directly (no
real render), since this file tests listing/filtering, not rendering.
"""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.produced_videos import list_produced_videos
from app.core.config import Settings
from app.db.base import Base
from app.modules.beat.models import Project
from app.modules.beat.project_service import create_project, set_project_render_job_id
from app.modules.beat.schemas import ProjectConfig
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _ProducedVideosTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.engine = create_engine(
            f"sqlite:///{self.tmp_path / 'test.db'}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(
            bind=self.engine, tables=[Project.__table__, VideoComposeJob.__table__, VideoComposeClip.__table__]
        )
        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.settings = Settings(library_dir=str(self.tmp_path))
        self.patcher = patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _db(self):
        return self.TestSessionLocal()

    def _list(self, **kwargs):
        db = self._db()
        try:
            return list_produced_videos(db=db, settings=self.settings, **kwargs)
        finally:
            db.close()

    def _insert_job(self, title: str, status: str = "completed") -> int:
        db = self._db()
        try:
            job = VideoComposeJob(
                title=title, script_text="script", status=status,
                created_at=_utcnow(), completed_at=_utcnow() if status == "completed" else None,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job.id
        finally:
            db.close()

    def _rendered_project(self, name: str, status: str = "completed") -> tuple[int, int]:
        project_id = create_project(name, "Script.", ProjectConfig())
        job_id = self._insert_job(f"job for {name}", status)
        set_project_render_job_id(project_id, job_id)
        return project_id, job_id


class ProducedVideosTests(_ProducedVideosTestCase):
    def test_empty(self):
        out = self._list()
        self.assertEqual(out.total, 0)
        self.assertEqual(out.items, [])

    def test_project_render_is_titled_after_the_project(self):
        project_id, job_id = self._rendered_project("Impossible Fact 001")

        out = self._list()
        self.assertEqual(out.total, 1)
        row = out.items[0]
        self.assertEqual(row.render_job_id, job_id)
        self.assertEqual(row.project_id, project_id)
        self.assertEqual(row.project_name, "Impossible Fact 001")
        self.assertEqual(row.title, "Impossible Fact 001")

    def test_job_without_project_uses_its_own_title(self):
        self._insert_job("Plain composer job")

        row = self._list().items[0]
        self.assertIsNone(row.project_id)
        self.assertEqual(row.title, "Plain composer job")

    def test_failed_hidden_by_default_but_shown_with_status_filter(self):
        self._rendered_project("Good")
        self._rendered_project("Bad", status="failed")

        self.assertEqual(self._list().total, 1)
        self.assertEqual(self._list(status="FAILED").total, 1)
        self.assertEqual(self._list(status="ALL").total, 2)

    def test_search_matches_title(self):
        self._rendered_project("Rules One")
        self._rendered_project("Rules Two")
        self._rendered_project("Twist Ending")

        self.assertEqual(self._list(q="rules").total, 2)
        self.assertEqual(self._list(q="Twist").total, 1)

    def test_pagination(self):
        for i in range(1, 6):
            self._rendered_project(f"P{i}")

        page1 = self._list(limit=2, offset=0)
        page2 = self._list(limit=2, offset=2)
        self.assertEqual(page1.total, 5)
        self.assertEqual(len(page1.items), 2)
        self.assertEqual(len(page2.items), 2)
        self.assertEqual(
            set(),
            {r.render_job_id for r in page1.items} & {r.render_job_id for r in page2.items},
        )


if __name__ == "__main__":
    unittest.main()
