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
from app.modules.documentary.models import DocumentaryProject, DocumentaryRenderJob
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
            bind=self.engine,
            tables=[Project.__table__, VideoComposeJob.__table__, VideoComposeClip.__table__, DocumentaryProject.__table__, DocumentaryRenderJob.__table__],
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



class DocumentaryVideosTests(_ProducedVideosTestCase):
    """Final renders of documentary projects appear next to Factory renders (Videos page)."""

    def _doc_job(self, project_id: int, status="succeeded", kind="final", name="output.mp4", with_file=True) -> int:
        out = self.tmp_path / "_documentary" / f"project_{project_id}" / "render" / f"job_{name}" / "output.mp4"
        if with_file:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"not a real video")
        db = self._db()
        try:
            job = DocumentaryRenderJob(
                project_id=project_id, kind=kind, status=status, input_hash=f"h{name}", params={}, output_path=str(out) if with_file else None,
                duration_sec=61.5, qc={"width": 1920, "height": 1080}, created_at=_utcnow(), finished_at=_utcnow(),
            )
            db.add(job)
            db.commit()
            return job.id
        finally:
            db.close()

    def _project(self, title="Phim thử") -> int:
        db = self._db()
        try:
            p = DocumentaryProject(title=title, topic="t")
            db.add(p)
            db.commit()
            return p.id
        finally:
            db.close()

    def test_final_render_is_listed_with_source_and_media_url(self):
        pid = self._project("Constantinople 1453")
        jid = self._doc_job(pid)
        with patch("app.api.v1.endpoints.produced_videos.ensure_thumbnail", return_value=None):
            result = self._list(status="ALL")
        doc = [i for i in result.items if i.source == "documentary"]
        self.assertEqual(len(doc), 1)
        self.assertEqual((doc[0].render_job_id, doc[0].title, doc[0].job_status), (jid, "Constantinople 1453", "COMPLETED"))
        self.assertEqual((doc[0].width, doc[0].height, doc[0].documentary_project_id), (1920, 1080, pid))
        self.assertTrue(doc[0].output_media_url.startswith("/media/_documentary/project_"))

    def test_previews_and_superseded_finals_are_not_listed(self):
        pid = self._project()
        self._doc_job(pid, kind="preview", name="p")
        old = self._doc_job(pid, name="old")
        new = self._doc_job(pid, name="new")
        with patch("app.api.v1.endpoints.produced_videos.ensure_thumbnail", return_value=None):
            ids = [i.render_job_id for i in self._list(status="ALL").items if i.source == "documentary"]
        self.assertEqual(ids, [new])  # newest successful final only
        self.assertNotIn(old, ids)

    def test_failed_final_only_shows_under_failed_filter(self):
        pid = self._project()
        self._doc_job(pid, status="failed", with_file=False)
        with patch("app.api.v1.endpoints.produced_videos.ensure_thumbnail", return_value=None):
            self.assertEqual([i for i in self._list().items if i.source == "documentary"], [])
            failed = [i for i in self._list(status="FAILED").items if i.source == "documentary"]
        self.assertEqual([i.job_status for i in failed], ["FAILED"])

    def test_factory_items_keep_working_and_are_labelled(self):
        self._insert_job("Video factory")
        pid = self._project()
        self._doc_job(pid)
        with patch("app.api.v1.endpoints.produced_videos.ensure_thumbnail", return_value=None):
            items = self._list().items
        self.assertEqual({i.source for i in items}, {"factory", "documentary"})
        self.assertEqual(items, sorted(items, key=lambda i: i.created_at, reverse=True))


if __name__ == "__main__":
    unittest.main()
