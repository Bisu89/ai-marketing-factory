"""Tests for app/api/v1/endpoints/produced_videos.py -- the read-only
browse of every finished Factory / Video Composer render. Reuses the same
real file-backed SQLite Batch/Project/VideoComposeJob harness the dashboard
tests use; VideoComposeJob rows are inserted directly (this file tests the
join/filter/facet aggregation, not the render pipeline).
"""

from datetime import datetime, timezone

from app.api.v1.endpoints.produced_videos import list_produced_videos
from app.modules.batch.service import set_item_fields
from app.modules.beat.models import Project
from app.modules.series.models import Series
from app.modules.video_composer.models import VideoComposeJob
from tests.api.test_batch_quality_gate import _QualityBatchTestCase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _ProducedVideosTestCase(_QualityBatchTestCase):
    def setUp(self):
        super().setUp()
        # The shared batch harness only creates its own fixed table list;
        # this endpoint also reads `series` (a Project may be a Series
        # episode), so create that one table here.
        Series.__table__.create(bind=self.engine, checkfirst=True)

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

    def _set_project_render_job(self, project_id: int, job_id: int) -> None:
        db = self._db()
        try:
            db.get(Project, project_id).render_job_id = job_id
            db.commit()
        finally:
            db.close()


class ProducedVideosTests(_ProducedVideosTestCase):
    def test_empty(self):
        out = self._list()
        self.assertEqual(out.total, 0)
        self.assertEqual(out.items, [])
        self.assertEqual(out.batches, [])
        self.assertEqual(out.series, [])

    def test_completed_job_via_batch_item_appears_with_batch_name(self):
        batch = self._create_batch("Impossible Fact", "custom", "A.\n---\nB.")
        job_id = self._insert_job("A")
        set_item_fields(batch.items[0].id, status="COMPLETED", render_job_id=job_id)

        out = self._list()
        self.assertEqual(out.total, 1)
        row = out.items[0]
        self.assertEqual(row.render_job_id, job_id)
        self.assertEqual(row.job_status, "COMPLETED")
        self.assertEqual(row.batch_name, "Impossible Fact")
        self.assertEqual(row.project_id, batch.items[0].project_id)
        self.assertEqual([(f.id, f.count) for f in out.batches], [(batch.id, 1)])

    def test_failed_hidden_by_default_but_shown_with_status_filter(self):
        batch = self._create_batch("B", "custom", "A.\n---\nB.")
        ok = self._insert_job("ok", "completed")
        bad = self._insert_job("bad", "failed")
        set_item_fields(batch.items[0].id, status="COMPLETED", render_job_id=ok)
        set_item_fields(batch.items[1].id, status="FAILED", render_job_id=bad)

        self.assertEqual({r.render_job_id for r in self._list().items}, {ok})
        self.assertEqual({r.render_job_id for r in self._list(status="FAILED").items}, {bad})
        self.assertEqual({r.render_job_id for r in self._list(status="ALL").items}, {ok, bad})

    def test_batch_and_search_filters(self):
        b1 = self._create_batch("Rules Batch", "custom", "A.\n---\nB.")
        b2 = self._create_batch("Twist Batch", "custom", "C.")
        j1 = self._insert_job("The Photograph")
        j2 = self._insert_job("The Mirror")
        j3 = self._insert_job("The Doorbell")
        set_item_fields(b1.items[0].id, status="COMPLETED", render_job_id=j1)
        set_item_fields(b1.items[1].id, status="COMPLETED", render_job_id=j2)
        set_item_fields(b2.items[0].id, status="COMPLETED", render_job_id=j3)

        self.assertEqual(self._list(batch_id=b1.id).total, 2)
        self.assertEqual(self._list(batch_id=b2.id).total, 1)
        # title comes from the project name ("<Batch> NNN"), and q matches it
        self.assertEqual(self._list(q="Twist Batch").total, 1)
        self.assertEqual(self._list(q="nonesuch").total, 0)
        # facets still list every batch that has a video, regardless of q
        self.assertEqual({f.id for f in self._list(q="Twist Batch").batches}, {b1.id, b2.id})

    def test_standalone_project_render_job_link(self):
        batch = self._create_batch("X", "custom", "A.")
        pid = batch.items[0].project_id
        job_id = self._insert_job("standalone")
        # No BatchItem.render_job_id set -- link only via Project.render_job_id
        self._set_project_render_job(pid, job_id)

        out = self._list()
        self.assertEqual(out.total, 1)
        self.assertEqual(out.items[0].project_id, pid)

    def test_pagination(self):
        batch = self._create_batch("P", "custom", "\n---\n".join(f"S{i}." for i in range(1, 6)))
        for item in batch.items:
            jid = self._insert_job(f"job {item.index}")
            set_item_fields(item.id, status="COMPLETED", render_job_id=jid)

        page1 = self._list(limit=2, offset=0)
        page2 = self._list(limit=2, offset=2)
        self.assertEqual(page1.total, 5)
        self.assertEqual(len(page1.items), 2)
        self.assertEqual(len(page2.items), 2)
        self.assertEqual(
            set(),
            {r.render_job_id for r in page1.items} & {r.render_job_id for r in page2.items},
        )
