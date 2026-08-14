"""Tests for app/api/v1/endpoints/dashboard.py (Task 17 -- see
docs/features/43-production-dashboard.md). Reuses tests.api.test_batch_render's
_BatchTestCase (real file-backed SQLite shared across Batch/Project/
VideoComposeJob) and tests.api.test_batch_quality_gate's _QualityBatchTestCase
helpers (_make_ready_item/_make_needs_review_item/_make_blocked_item), same
as Task 16's own batch integration tests. VideoComposeJob rows for
RUNNING/COMPLETED/FAILED/QUEUED scenarios are inserted directly (not via a
real ffmpeg render) -- this file tests dashboard *aggregation*, not the
render pipeline itself, which is already covered elsewhere.
"""

import unittest
from datetime import datetime, timedelta, timezone

from app.api.v1.endpoints.dashboard import build_dashboard
from app.modules.batch.service import set_batch_status, set_item_fields
from app.modules.video_composer.models import VideoComposeJob
from tests.api.test_batch_quality_gate import _QualityBatchTestCase
from tests.api.test_batch_render import _make_solid_image


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _DashboardTestCase(_QualityBatchTestCase):
    def setUp(self):
        super().setUp()
        self.image = _make_solid_image(self.tmp_path / "shared.jpg", (10, 200, 10))
        self.asset_id = self._register_image_asset(self.image)
        self.low_res_image = _make_solid_image(self.tmp_path / "low_res.jpg", (40, 40, 200), size=(200, 200))
        self.low_res_asset_id = self._register_low_res_image_asset(self.low_res_image)

    def _dashboard(self):
        db = self._db()
        try:
            return build_dashboard(db, self.settings)
        finally:
            db.close()

    def _insert_job(
        self, title: str, status: str,
        created_at: datetime | None = None, completed_at: datetime | None = None,
        progress_current: int | None = None, progress_total: int | None = None,
        error_message: str | None = None,
    ) -> int:
        db = self._db()
        try:
            job = VideoComposeJob(
                title=title, script_text="script", status=status,
                created_at=created_at or _utcnow(), completed_at=completed_at,
                render_progress_current=progress_current, render_progress_total=progress_total,
                error_message=error_message,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job.id
        finally:
            db.close()

    def _link_job_to_item(self, item, job_id: int, item_status: str) -> None:
        set_item_fields(item.id, status=item_status, render_job_id=job_id, error_message=None)


class EmptyStateTests(_QualityBatchTestCase):
    def test_no_batches_no_jobs_is_empty(self):
        db = self._db()
        try:
            out = build_dashboard(db, self.settings)
        finally:
            db.close()

        self.assertFalse(out.has_any_data)
        self.assertEqual(out.summary.ready, 0)
        self.assertEqual(out.summary.needs_review, 0)
        self.assertEqual(out.summary.blocked, 0)
        self.assertEqual(out.summary.rendering, 0)
        self.assertEqual(out.summary.completed_today, 0)
        self.assertIsNone(out.current_batch)
        self.assertIsNone(out.current_render)
        self.assertEqual(out.attention, [])
        self.assertEqual(out.attention_total, 0)
        self.assertEqual(out.recent_videos, [])
        self.assertEqual(out.recent_failures, [])
        self.assertEqual(out.queue, [])
        self.assertEqual(out.cost.external_video_api_calls, 0)
        self.assertEqual(out.cost.external_video_api_cost, 0.0)


class SummaryAggregationTests(_DashboardTestCase):
    def test_twelve_projects_six_ready_two_review_one_blocked_one_running_two_completed(self):
        # Task 17 section 42's own literal acceptance fixture.
        scripts = "\n---\n".join(f"Script {i}." for i in range(1, 13))
        out = self._create_batch("Dashboard Fixture", "custom", scripts)
        self.assertEqual(len(out.items), 12)

        for item in out.items[0:6]:
            self._make_ready_item(item, self.asset_id)
        for item in out.items[6:8]:
            self._make_needs_review_item(item, self.low_res_asset_id)
        self._make_blocked_item(out.items[8], self.asset_id)
        set_item_fields(out.items[8].id, status="SKIPPED", error_message="Quality Gate: blocked")

        running_job_id = self._insert_job("Running project", "rendering_beats", progress_current=2, progress_total=5)
        self._link_job_to_item(out.items[9], running_job_id, "RENDERING")

        for item in out.items[10:12]:
            job_id = self._insert_job(f"Done {item.index}", "completed", completed_at=_utcnow())
            self._link_job_to_item(item, job_id, "COMPLETED")

        dashboard = self._dashboard()
        self.assertEqual(dashboard.summary.ready, 6)
        self.assertEqual(dashboard.summary.needs_review, 2)
        self.assertEqual(dashboard.summary.blocked, 1)
        self.assertEqual(dashboard.summary.rendering, 1)
        self.assertEqual(dashboard.summary.completed_today, 2)
        self.assertTrue(dashboard.has_any_data)


class BatchProgressTests(_DashboardTestCase):
    def test_batch_a_ten_projects_matches_real_item_counts(self):
        # Task 17 section 43's own literal fixture: 10 projects, 6
        # completed, 1 rendering, 2 queued (not yet rendering), 1 blocked.
        scripts = "\n---\n".join(f"Script {i}." for i in range(1, 11))
        out = self._create_batch("Batch A", "custom", scripts)
        set_batch_status(out.id, "PROCESSING")

        for item in out.items[0:6]:
            job_id = self._insert_job(f"Done {item.index}", "completed", completed_at=_utcnow())
            self._link_job_to_item(item, job_id, "COMPLETED")

        running_job_id = self._insert_job("Running", "merging")
        self._link_job_to_item(out.items[6], running_job_id, "RENDERING")

        # items 7, 8 stay PROJECT_CREATED/BEATS_READY -- "not yet rendering"
        set_item_fields(out.items[8].id, status="BEATS_READY", error_message=None)

        set_item_fields(out.items[9].id, status="SKIPPED", error_message="Quality Gate: blocked")

        dashboard = self._dashboard()
        self.assertIsNotNone(dashboard.current_batch)
        self.assertEqual(dashboard.current_batch.batch_id, out.id)
        self.assertEqual(dashboard.current_batch.total, 10)
        self.assertEqual(dashboard.current_batch.completed, 6)
        self.assertEqual(dashboard.current_batch.status_counts.get("COMPLETED"), 6)
        self.assertEqual(dashboard.current_batch.status_counts.get("RENDERING"), 1)
        self.assertEqual(dashboard.current_batch.status_counts.get("SKIPPED"), 1)
        self.assertEqual(
            dashboard.current_batch.status_counts.get("PROJECT_CREATED", 0)
            + dashboard.current_batch.status_counts.get("BEATS_READY", 0),
            2,
        )

    def test_most_recently_created_active_batch_wins_when_multiple_active(self):
        older = self._create_batch("Older Active", "custom", "One.")
        set_batch_status(older.id, "PROCESSING")
        newer = self._create_batch("Newer Active", "custom", "One.")
        set_batch_status(newer.id, "PROCESSING")

        dashboard = self._dashboard()
        self.assertEqual(dashboard.current_batch.batch_id, newer.id)

    def test_no_active_batch_yields_no_current_batch(self):
        out = self._create_batch("Draft Only", "custom", "One.")
        self.assertEqual(out.status, "DRAFT")

        dashboard = self._dashboard()
        self.assertIsNone(dashboard.current_batch)


class CurrentRenderAndQueueTests(_DashboardTestCase):
    def test_running_job_reports_phase_progress_and_project_name(self):
        out = self._create_batch("Render Now", "custom", "One.")
        job_id = self._insert_job(
            "fallback title", "rendering_beats",
            created_at=_utcnow() - timedelta(seconds=8), progress_current=3, progress_total=5,
        )
        self._link_job_to_item(out.items[0], job_id, "RENDERING")

        dashboard = self._dashboard()
        self.assertIsNotNone(dashboard.current_render)
        self.assertEqual(dashboard.current_render.render_job_id, job_id)
        self.assertEqual(dashboard.current_render.project_id, out.items[0].project_id)
        self.assertEqual(dashboard.current_render.project_name, "Render Now 001")
        self.assertEqual(dashboard.current_render.phase, "RENDER_BEATS")
        self.assertEqual(dashboard.current_render.progress_current, 3)
        self.assertEqual(dashboard.current_render.progress_total, 5)
        self.assertGreaterEqual(dashboard.current_render.elapsed_seconds, 8.0)

    def test_no_running_job_yields_no_current_render(self):
        dashboard = self._dashboard()
        self.assertIsNone(dashboard.current_render)

    def test_queue_lists_running_first_then_queued_in_fifo_order(self):
        out = self._create_batch("Queue Test", "custom", "One.\n---\nTwo.\n---\nThree.")
        running_job_id = self._insert_job("Running", "merging")
        self._link_job_to_item(out.items[0], running_job_id, "RENDERING")
        first_queued = self._insert_job("First queued", "queued", created_at=_utcnow() - timedelta(seconds=5))
        self._link_job_to_item(out.items[1], first_queued, "RENDERING")
        second_queued = self._insert_job("Second queued", "queued", created_at=_utcnow())
        self._link_job_to_item(out.items[2], second_queued, "RENDERING")

        dashboard = self._dashboard()
        job_statuses = [(entry.render_job_id, entry.job_status) for entry in dashboard.queue]
        self.assertEqual(
            job_statuses,
            [(running_job_id, "RUNNING"), (first_queued, "QUEUED"), (second_queued, "QUEUED")],
        )

    def test_completed_job_never_appears_in_queue(self):
        out = self._create_batch("No Queue", "custom", "One.")
        job_id = self._insert_job("Done", "completed", completed_at=_utcnow())
        self._link_job_to_item(out.items[0], job_id, "COMPLETED")

        dashboard = self._dashboard()
        self.assertEqual(dashboard.queue, [])


class AttentionTests(_DashboardTestCase):
    def test_priority_order_is_blocked_then_failed_then_needs_review(self):
        out = self._create_batch("Attention Order", "custom", "One.\n---\nTwo.\n---\nThree.")
        self._make_needs_review_item(out.items[0], self.low_res_asset_id)
        set_item_fields(out.items[1].id, status="FAILED", error_message="Render failed: ffmpeg exit 1")
        set_item_fields(out.items[2].id, status="SKIPPED", error_message="Quality Gate: Beat 01 has no assigned visual asset.")

        dashboard = self._dashboard()
        priorities = [entry.priority for entry in dashboard.attention]
        self.assertEqual(priorities, ["BLOCKED", "FAILED", "NEEDS_REVIEW"])

    def test_limited_to_five_with_total_reported(self):
        scripts = "\n---\n".join(f"Script {i}." for i in range(1, 8))
        out = self._create_batch("Attention Overflow", "custom", scripts)
        for item in out.items:
            set_item_fields(item.id, status="FAILED", error_message="Render failed.")

        dashboard = self._dashboard()
        self.assertEqual(len(dashboard.attention), 5)
        self.assertEqual(dashboard.attention_total, 7)

    def test_ready_items_are_not_flagged(self):
        out = self._create_batch("All Good", "custom", "One.")
        self._make_ready_item(out.items[0], self.asset_id)

        dashboard = self._dashboard()
        self.assertEqual(dashboard.attention, [])


class RecentVideosTests(_DashboardTestCase):
    def test_recent_completed_and_failed_are_reported_separately(self):
        out = self._create_batch("Recents", "custom", "One.\n---\nTwo.")
        completed_job = self._insert_job("Completed one", "completed", completed_at=_utcnow())
        self._link_job_to_item(out.items[0], completed_job, "COMPLETED")
        failed_job = self._insert_job(
            "Failed one", "failed", completed_at=_utcnow(), error_message="OUTPUT_VALIDATION_FAILED"
        )
        self._link_job_to_item(out.items[1], failed_job, "FAILED")

        dashboard = self._dashboard()
        self.assertEqual(len(dashboard.recent_videos), 1)
        self.assertEqual(dashboard.recent_videos[0].render_job_id, completed_job)
        self.assertEqual(dashboard.recent_videos[0].status, "COMPLETED")

        self.assertEqual(len(dashboard.recent_failures), 1)
        self.assertEqual(dashboard.recent_failures[0].render_job_id, failed_job)
        self.assertEqual(dashboard.recent_failures[0].status, "FAILED")
        self.assertEqual(dashboard.recent_failures[0].error_message, "OUTPUT_VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
