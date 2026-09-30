"""Tests for app/api/v1/endpoints/dashboard.py (Task 17 -- see
docs/features/43-production-dashboard.md). A real file-backed SQLite shared
across Project/Asset/VideoComposeJob/FactoryRun. VideoComposeJob and
FactoryRun rows for RUNNING/COMPLETED/FAILED/QUEUED scenarios are inserted
directly (not via a real ffmpeg render or Factory run) -- this file tests
dashboard *aggregation*, not the render pipeline itself, which is already
covered elsewhere.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.dashboard import build_dashboard
from app.core.config import Settings
from app.db.base import Base
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.beat.models import Project
from app.modules.beat.project_service import create_project, set_project_render_job_id, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType, ProjectConfig
from app.modules.factory.models import FactoryCheckpoint, FactoryRun
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob
from tests.api.media_helpers import _make_solid_image


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _DashboardTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.engine = create_engine(
            f"sqlite:///{self.tmp_path / 'test.db'}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Project.__table__, Asset.__table__, VideoComposeJob.__table__, VideoComposeClip.__table__,
                FactoryRun.__table__, FactoryCheckpoint.__table__,
            ],
        )
        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.settings = Settings(library_dir=str(self.tmp_path))
        self.patcher = patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal)
        self.patcher.start()

        # Unknown dimensions (no width/height) are never flagged as low
        # resolution; the 200x200 one always is.
        self.asset_id = self._register_image(_make_solid_image(self.tmp_path / "shared.jpg", (10, 200, 10)))
        self.low_res_asset_id = self._register_image(
            _make_solid_image(self.tmp_path / "low_res.jpg", (40, 40, 200), size=(200, 200)), size=200
        )

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _db(self):
        return self.TestSessionLocal()

    def _register_image(self, path: Path, size: int | None = None) -> int:
        db = self._db()
        try:
            asset = AssetService(db).register(
                AssetRegisterIn(filename=path.name, path=str(path), type="image", source="test", width=size, height=size)
            )
            return asset.id
        finally:
            db.close()

    def _dashboard(self):
        db = self._db()
        try:
            return build_dashboard(db, self.settings)
        finally:
            db.close()

    # -- Projects in each Quality Gate state -------------------------------

    def _project(self, name: str, beats: list[Beat] | None = None) -> int:
        project_id = create_project(name, "Script.", ProjectConfig())
        if beats is not None:
            plan = BeatPlan(script_text="Script.", beats=beats, project_name=name)
            plan.config.render.profile = "PREVIEW"
            update_project_beat_plan(project_id, plan)
        return project_id

    def _ready_project(self, name: str) -> int:
        # No visual_hint at all -> confidence defaults to HIGH (nothing to
        # contradict the assignment); real narration; single well-paced beat.
        return self._project(name, [
            Beat(id="beat_01", order=1, type=BeatType.BODY, narration="A real, complete sentence of narration.",
                 duration=2.0, asset_id=self.asset_id),
        ])

    def _needs_review_project(self, name: str) -> int:
        # Several real, non-blocking warnings across two dimensions (a
        # pacing outlier + low-resolution/low-confidence visual matches on
        # every beat) -- reliably NEEDS_REVIEW without any error-severity issue.
        hint = "a completely unrelated concept with different wording"
        return self._project(name, [
            Beat(id="beat_01", order=1, type=BeatType.BODY, narration="Narration text one.", duration=2.0,
                 asset_id=self.low_res_asset_id, visual_hint=hint),
            Beat(id="beat_02", order=2, type=BeatType.BODY, narration="Narration text two.", duration=2.0,
                 asset_id=self.low_res_asset_id, visual_hint=hint),
            Beat(id="beat_03", order=3, type=BeatType.BODY, narration="Narration text three.", duration=20.0,
                 asset_id=self.low_res_asset_id, visual_hint=hint),
        ])

    def _blocked_project(self, name: str) -> int:
        # A real asset, but no narration while narration is enabled -- only
        # the Quality Gate catches this.
        return self._project(name, [
            Beat(id="beat_01", order=1, type=BeatType.BODY, narration=None, duration=2.0, asset_id=self.asset_id),
        ])

    # -- Direct row inserts -------------------------------------------------

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

    def _insert_run(self, project_id: int, status: str, error_message: str | None = None) -> None:
        db = self._db()
        try:
            db.add(FactoryRun(project_id=project_id, status=status, error_message=error_message))
            db.commit()
        finally:
            db.close()


class EmptyStateTests(_DashboardTestCase):
    def test_no_projects_no_jobs_is_empty(self):
        out = self._dashboard()

        self.assertFalse(out.has_any_data)
        self.assertEqual(out.summary.ready, 0)
        self.assertEqual(out.summary.needs_review, 0)
        self.assertEqual(out.summary.blocked, 0)
        self.assertEqual(out.summary.rendering, 0)
        self.assertEqual(out.summary.completed_today, 0)
        self.assertIsNone(out.current_render)
        self.assertEqual(out.attention, [])
        self.assertEqual(out.attention_total, 0)
        self.assertEqual(out.recent_videos, [])
        self.assertEqual(out.recent_failures, [])
        self.assertEqual(out.queue, [])
        self.assertEqual(out.pipeline.total_items, 0)
        self.assertEqual(out.cost.external_video_api_calls, 0)
        self.assertEqual(out.cost.external_video_api_cost, 0.0)


class SummaryAggregationTests(_DashboardTestCase):
    def test_six_ready_two_review_one_blocked_one_running_two_completed(self):
        for i in range(6):
            self._ready_project(f"Ready {i}")
        for i in range(2):
            self._needs_review_project(f"Review {i}")
        self._blocked_project("Blocked")

        running = self._ready_project("Running")
        set_project_render_job_id(running, self._insert_job("Running", "rendering_beats", progress_current=2, progress_total=5))
        for i in range(2):
            done = self._ready_project(f"Done {i}")
            set_project_render_job_id(done, self._insert_job(f"Done {i}", "completed", completed_at=_utcnow()))

        dashboard = self._dashboard()
        # Rendered projects are never re-judged by the Quality Gate.
        self.assertEqual(dashboard.summary.ready, 6)
        self.assertEqual(dashboard.summary.needs_review, 2)
        self.assertEqual(dashboard.summary.blocked, 1)
        self.assertEqual(dashboard.summary.rendering, 1)
        self.assertEqual(dashboard.summary.completed_today, 2)
        self.assertTrue(dashboard.has_any_data)

    def test_project_under_needs_review_run_is_rechecked(self):
        project_id = self._ready_project("Fixed since review")
        self._insert_run(project_id, "NEEDS_REVIEW")

        dashboard = self._dashboard()
        self.assertEqual(dashboard.summary.ready, 1)

    def test_project_with_active_run_is_not_judged(self):
        project_id = self._blocked_project("In flight")
        self._insert_run(project_id, "GENERATING_VOICE")

        dashboard = self._dashboard()
        self.assertEqual(dashboard.summary.blocked, 0)
        self.assertEqual(dashboard.attention, [])


class CurrentRenderAndQueueTests(_DashboardTestCase):
    def test_running_job_reports_phase_progress_and_project_name(self):
        project_id = self._ready_project("Render Now")
        job_id = self._insert_job(
            "fallback title", "rendering_beats",
            created_at=_utcnow() - timedelta(seconds=8), progress_current=3, progress_total=5,
        )
        set_project_render_job_id(project_id, job_id)

        dashboard = self._dashboard()
        self.assertIsNotNone(dashboard.current_render)
        self.assertEqual(dashboard.current_render.render_job_id, job_id)
        self.assertEqual(dashboard.current_render.project_id, project_id)
        self.assertEqual(dashboard.current_render.project_name, "Render Now")
        self.assertEqual(dashboard.current_render.phase, "RENDER_BEATS")
        self.assertEqual(dashboard.current_render.progress_current, 3)
        self.assertEqual(dashboard.current_render.progress_total, 5)
        self.assertGreaterEqual(dashboard.current_render.elapsed_seconds, 8.0)

    def test_job_without_project_falls_back_to_its_own_title(self):
        self._insert_job("Plain composer job", "merging")

        dashboard = self._dashboard()
        self.assertIsNone(dashboard.current_render.project_id)
        self.assertEqual(dashboard.current_render.project_name, "Plain composer job")

    def test_no_running_job_yields_no_current_render(self):
        dashboard = self._dashboard()
        self.assertIsNone(dashboard.current_render)

    def test_queue_lists_running_first_then_queued_in_fifo_order(self):
        running_job_id = self._insert_job("Running", "merging")
        first_queued = self._insert_job("First queued", "queued", created_at=_utcnow() - timedelta(seconds=5))
        second_queued = self._insert_job("Second queued", "queued", created_at=_utcnow())

        dashboard = self._dashboard()
        job_statuses = [(entry.render_job_id, entry.job_status) for entry in dashboard.queue]
        self.assertEqual(
            job_statuses,
            [(running_job_id, "RUNNING"), (first_queued, "QUEUED"), (second_queued, "QUEUED")],
        )

    def test_completed_job_never_appears_in_queue(self):
        self._insert_job("Done", "completed", completed_at=_utcnow())

        dashboard = self._dashboard()
        self.assertEqual(dashboard.queue, [])


class AttentionTests(_DashboardTestCase):
    def test_priority_order_is_blocked_then_failed_then_needs_review(self):
        self._needs_review_project("Review me")
        failed = self._ready_project("Failed run")
        self._insert_run(failed, "FAILED", error_message="Render failed: ffmpeg exit 1")
        self._blocked_project("Blocked")

        dashboard = self._dashboard()
        self.assertEqual([entry.priority for entry in dashboard.attention], ["BLOCKED", "FAILED", "NEEDS_REVIEW"])
        failed_entry = next(e for e in dashboard.attention if e.priority == "FAILED")
        self.assertEqual(failed_entry.project_id, failed)
        self.assertEqual(failed_entry.reason, "Render failed: ffmpeg exit 1")

    def test_limited_to_five_with_total_reported(self):
        for i in range(7):
            self._insert_run(self._project(f"Failed {i}"), "FAILED")

        dashboard = self._dashboard()
        self.assertEqual(len(dashboard.attention), 5)
        self.assertEqual(dashboard.attention_total, 7)

    def test_ready_projects_are_not_flagged(self):
        self._ready_project("All Good")

        dashboard = self._dashboard()
        self.assertEqual(dashboard.attention, [])


class PipelineTests(_DashboardTestCase):
    def test_counts_each_projects_latest_run_only(self):
        a = self._project("A")
        self._insert_run(a, "FAILED")
        self._insert_run(a, "COMPLETED")  # a retry that succeeded -- supersedes the failure
        b = self._project("B")
        self._insert_run(b, "NEEDS_REVIEW")
        self._project("C")  # never run

        dashboard = self._dashboard()
        self.assertEqual(dashboard.pipeline.total_items, 2)
        self.assertEqual(dashboard.pipeline.status_counts, {"COMPLETED": 1, "NEEDS_REVIEW": 1})


class RecentVideosTests(_DashboardTestCase):
    def test_recent_completed_and_failed_are_reported_separately(self):
        done = self._ready_project("Completed one")
        completed_job = self._insert_job("Completed one", "completed", completed_at=_utcnow())
        set_project_render_job_id(done, completed_job)
        failed_job = self._insert_job(
            "Failed one", "failed", completed_at=_utcnow(), error_message="OUTPUT_VALIDATION_FAILED"
        )

        dashboard = self._dashboard()
        self.assertEqual(len(dashboard.recent_videos), 1)
        self.assertEqual(dashboard.recent_videos[0].render_job_id, completed_job)
        self.assertEqual(dashboard.recent_videos[0].project_id, done)
        self.assertEqual(dashboard.recent_videos[0].status, "COMPLETED")

        self.assertEqual(len(dashboard.recent_failures), 1)
        self.assertEqual(dashboard.recent_failures[0].render_job_id, failed_job)
        self.assertEqual(dashboard.recent_failures[0].status, "FAILED")
        self.assertEqual(dashboard.recent_failures[0].error_message, "OUTPUT_VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
