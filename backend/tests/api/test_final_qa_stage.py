"""Tests for Task 28 -- see docs/features/54-final-qa.md. Reuses
tests.api.test_package_stage's own _PackageStageTestCase harness (real
LocalTTSProvider, real FFmpeg Motion/Final-Composer rendering, real Audio
Master mixing, real Captions, real Pillow/FFmpeg thumbnail extraction) --
no mocking of any pipeline stage, the same "exercise the real engine"
precedent every prior stage's own tests already established.
"""

import json
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.v1.endpoints.audio_generate import audio_master_path
from app.api.v1.endpoints.caption_generate import captions_ass_path
from app.api.v1.endpoints.factory_pipeline import (
    FactoryStageError,
    _run_final_qa_and_settle,
    _stage_final_qa,
    continue_run,
    reconcile_factory_runs_on_startup,
    retry_run,
)
from app.api.v1.endpoints.final_qa import get_project_final_qa, get_qa_report, qa_report_path, regenerate_final_qa, run_final_qa
from app.api.v1.endpoints.package_generate import metadata_path, thumbnail_path
from app.modules.beat.project_service import get_project_draft
from app.modules.factory import service as factory_service
from app.modules.video_composer.models import VideoComposeJob
from tests.api.test_batch_render import FFMPEG_AVAILABLE
from tests.api.test_package_stage import _PackageStageTestCase


def _artifact_paths(case: _PackageStageTestCase, project_id: int) -> dict[str, Path]:
    draft = get_project_draft(project_id)
    db = case.TestSessionLocal()
    try:
        job = db.get(VideoComposeJob, draft.render_job_id)
        video_path = Path(job.output_path)
        thumb_file = thumbnail_path(job)
        meta_file = metadata_path(job)
        report_file = qa_report_path(job)
    finally:
        db.close()
    return {
        "video": video_path, "thumbnail": thumb_file, "metadata": meta_file,
        "captions": captions_ass_path(project_id, case.settings.library_dir),
        "audio": audio_master_path(project_id, case.settings.library_dir),
        "report": report_file,
    }


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class EndToEndFinalQaTests(_PackageStageTestCase):
    def test_full_pipeline_reaches_completed_with_a_qa_pass_and_a_persisted_report(self):
        project_id = self._full_pipeline_project(
            "Final QA E2E", ["This is the amazing hook.", "This is the main story now.", "And that's the ending."],
            content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")
        self.assertIn(run.qa_status, ("PASS", "PASS_WITH_WARNINGS"))
        self.assertIsNotNone(run.qa_score)
        self.assertGreater(run.qa_score, 0)

        paths = _artifact_paths(self, project_id)
        self.assertTrue(paths["report"].exists())
        data = json.loads(paths["report"].read_text(encoding="utf-8"))
        self.assertEqual(data["status"], run.qa_status)
        self.assertEqual(data["score"], run.qa_score)
        self.assertGreater(len(data["checks"]), 0)

    def test_get_and_regenerate_final_qa_endpoints_agree(self):
        project_id = self._full_pipeline_project(
            "Final QA Endpoints", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        fetched = get_project_final_qa(project_id, self.settings)
        self.assertIsNotNone(fetched["report"])
        self.assertEqual(fetched["report"]["status"], run.qa_status)

        regenerated = regenerate_final_qa(project_id, self.settings)
        self.assertEqual(regenerated["report"]["status"], run.qa_status)

    def test_no_completed_render_yet_produces_a_graceful_fail_not_an_exception(self):
        from app.modules.beat.project_service import create_project
        from app.modules.beat.schemas import ProjectConfig

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("Never Rendered QA", "placeholder", ProjectConfig())

        report = run_final_qa(project_id, self.settings)
        self.assertEqual(report.status, "FAIL")
        package_check = next(c for c in report.checks if c.code == "PACKAGE_INCOMPLETE")
        self.assertEqual(package_check.status, "FAIL")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class FinalQaFailureDetectionTests(_PackageStageTestCase):
    def test_missing_thumbnail_produces_fail_with_repair_stage_thumbnail(self):
        project_id = self._full_pipeline_project(
            "Missing Thumbnail QA", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        paths = _artifact_paths(self, project_id)
        paths["thumbnail"].unlink()

        report = run_final_qa(project_id, self.settings)
        self.assertEqual(report.status, "FAIL")
        thumb_fail = next(c for c in report.failures if c.code == "THUMBNAIL_INVALID")
        self.assertEqual(thumb_fail.repair_stage, "THUMBNAIL")

    def test_regenerating_audio_master_after_render_is_detected_as_a_stale_dependency(self):
        project_id = self._full_pipeline_project(
            "Stale Dependency QA", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        paths = _artifact_paths(self, project_id)
        future = time.time() + 100
        os.utime(paths["audio"], (future, future))

        report = run_final_qa(project_id, self.settings)
        self.assertEqual(report.status, "FAIL")
        stale = next(c for c in report.failures if c.code == "STALE_DEPENDENCY")
        self.assertEqual(stale.repair_stage, "RENDER")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class NeedsReviewSettleTests(_PackageStageTestCase):
    def test_qa_fail_settles_the_run_to_needs_review_with_failed_stage_final_qa(self):
        project_id = self._full_pipeline_project(
            "QA Fail Settle", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        paths = _artifact_paths(self, project_id)
        paths["thumbnail"].unlink()

        factory_service.set_run_fields(run.id, status="FINAL_QA")
        _run_final_qa_and_settle(run.id, project_id, self.settings)

        after = factory_service.get_run(run.id)
        self.assertEqual(after.status, "NEEDS_REVIEW")
        self.assertEqual(after.failed_stage, "FINAL_QA")
        self.assertEqual(after.qa_status, "FAIL")
        self.assertTrue(after.requires_human_review)
        self.assertGreaterEqual(after.review_reason_count, 1)
        # Section: validate_package (Task 27) itself already checks for a
        # real thumbnail file, so a missing thumbnail.jpg trips
        # check_package_complete (which runs first) in addition to its own
        # dedicated THUMBNAIL_INVALID check -- the run's own error_code is
        # whichever FAIL check happens to be first, but the thumbnail
        # problem must still show up somewhere in the full check list.
        self.assertIn(after.error_code, ("PACKAGE_INCOMPLETE", "THUMBNAIL_INVALID"))
        report = get_qa_report(project_id, self.settings)
        self.assertTrue(any(c.code == "THUMBNAIL_INVALID" for c in report.failures))

    def test_qa_pass_settles_the_run_to_completed(self):
        project_id = self._full_pipeline_project(
            "QA Pass Settle", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        factory_service.set_run_fields(run.id, status="FINAL_QA", completed_at=None)
        _run_final_qa_and_settle(run.id, project_id, self.settings)

        after = factory_service.get_run(run.id)
        self.assertEqual(after.status, "COMPLETED")
        self.assertIn(after.qa_status, ("PASS", "PASS_WITH_WARNINGS"))
        self.assertFalse(after.requires_human_review)


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class ContinueAndRetryFinalQaTests(_PackageStageTestCase):
    def test_continue_after_fixing_the_problem_resolves_to_completed(self):
        project_id = self._full_pipeline_project(
            "Continue Final QA", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        paths = _artifact_paths(self, project_id)
        paths["thumbnail"].unlink()
        factory_service.set_run_fields(run.id, status="FINAL_QA")
        _run_final_qa_and_settle(run.id, project_id, self.settings)
        needs_review = factory_service.get_run(run.id)
        self.assertEqual(needs_review.status, "NEEDS_REVIEW")
        self.assertEqual(needs_review.failed_stage, "FINAL_QA")

        from app.api.v1.endpoints.package_generate import regenerate_thumbnail

        regenerate_thumbnail(project_id, self.settings)  # fix it

        continue_run(run.id, self.settings, self.service)
        deadline = time.monotonic() + 30
        current = factory_service.get_run(run.id)
        while time.monotonic() < deadline and current.status == "FINAL_QA":
            time.sleep(0.1)
            current = factory_service.get_run(run.id)
        self.assertEqual(current.status, "COMPLETED")
        self.assertIsNone(current.failed_stage)

    def test_retry_from_final_qa_unexpected_error_resumes_and_completes(self):
        project_id = self._full_pipeline_project(
            "Retry Final QA Crash", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")
        original_render_job_id = run.render_job_id

        # Simulate a crash mid-FINAL_QA that left the run FAILED (never a
        # QA FAIL outcome -- that's NEEDS_REVIEW, see NeedsReviewSettleTests
        # above -- this is the genuine "something threw" recovery path).
        factory_service.set_run_fields(
            run.id, status="FAILED", failed_stage="FINAL_QA", error_code="UNEXPECTED_ERROR",
            error_message="simulated crash", completed_at=None,
        )

        retried = retry_run(run.id, self.settings, self.service)
        self.assertEqual(retried.status, "COMPLETED")
        self.assertEqual(retried.render_job_id, original_render_job_id)  # never re-rendered

    def test_retry_from_packaging_still_passes_through_final_qa(self):
        project_id = self._full_pipeline_project(
            "Retry Packaging Then QA", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")
        original_render_job_id = run.render_job_id

        factory_service.set_run_fields(
            run.id, status="FAILED", failed_stage="PACKAGING", error_code="FACTORY_INTERRUPTED",
            error_message="simulated crash", completed_at=None,
        )
        retried = retry_run(run.id, self.settings, self.service)
        self.assertEqual(retried.status, "COMPLETED")
        self.assertEqual(retried.render_job_id, original_render_job_id)
        self.assertIsNotNone(retried.qa_status)


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class CrashRecoveryFinalQaTests(_PackageStageTestCase):
    def test_run_stuck_in_final_qa_is_marked_interrupted_on_reconcile(self):
        project_id = self._full_pipeline_project(
            "Final QA Crash Reconcile", ["Some narration text."], content_brief=self._content_brief(),
        )
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="FINAL_QA")

        reconciled = reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)

        after = factory_service.get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.error_code, "FACTORY_INTERRUPTED")
        self.assertEqual(after.failed_stage, "FINAL_QA")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class IdempotencyAndNoMutationTests(_PackageStageTestCase):
    def test_running_qa_twice_produces_the_same_result(self):
        project_id = self._full_pipeline_project(
            "QA Idempotency", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        first = get_qa_report(project_id, self.settings)
        second = run_final_qa(project_id, self.settings)
        self.assertEqual(first.status, second.status)
        self.assertEqual(first.score, second.score)
        self.assertEqual([c.code for c in first.checks], [c.code for c in second.checks])
        self.assertEqual([c.status for c in first.checks], [c.status for c in second.checks])

    def test_qa_never_mutates_any_of_the_produced_artifacts(self):
        project_id = self._full_pipeline_project(
            "QA No Mutation", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        paths = _artifact_paths(self, project_id)
        before = {
            key: path.read_bytes() for key, path in paths.items()
            if key != "report" and path.exists()
        }
        run_final_qa(project_id, self.settings)
        run_final_qa(project_id, self.settings)
        for key, content in before.items():
            self.assertEqual(paths[key].read_bytes(), content, f"{key} was mutated by Final QA")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class StageErrorTranslationTests(_PackageStageTestCase):
    def test_final_qa_never_raises_for_a_normal_qa_fail_outcome(self):
        # Section: run_final_qa is designed to never raise for any expected
        # outcome, including FAIL -- _stage_final_qa should hand back a
        # real QAReport, not a FactoryStageError, for a plain FAIL.
        project_id = self._full_pipeline_project(
            "QA Stage Never Raises", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")
        paths = _artifact_paths(self, project_id)
        paths["thumbnail"].unlink()

        report = _stage_final_qa(project_id, self.settings)
        self.assertEqual(report.status, "FAIL")

    def test_an_unexpected_exception_during_final_qa_marks_the_run_failed(self):
        project_id = self._full_pipeline_project(
            "QA Stage Unexpected Error", ["Some narration text."], content_brief=self._content_brief(),
        )
        run = self._render_and_wait(project_id)
        self.assertEqual(run.status, "COMPLETED")

        factory_service.set_run_fields(run.id, status="FINAL_QA", completed_at=None)
        with patch(
            "app.api.v1.endpoints.factory_pipeline.run_final_qa", side_effect=RuntimeError("boom"),
        ):
            _run_final_qa_and_settle(run.id, project_id, self.settings)

        after = factory_service.get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.failed_stage, "FINAL_QA")
        self.assertEqual(after.error_code, "UNEXPECTED_ERROR")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class MultiProjectQaTests(_PackageStageTestCase):
    def test_three_projects_two_pass_one_needs_review(self):
        good_ids = [
            self._full_pipeline_project(f"Multi QA Good {i}", [f"Narration number {i}."], content_brief=self._content_brief())
            for i in range(1, 3)
        ]
        broken_id = self._full_pipeline_project(
            "Multi QA Broken", ["Narration for the broken one."], content_brief=self._content_brief(),
        )

        for project_id in good_ids:
            run = self._render_and_wait(project_id)
            self.assertEqual(run.status, "COMPLETED")
            self.assertIn(run.qa_status, ("PASS", "PASS_WITH_WARNINGS"))

        run = self._render_and_wait(broken_id)
        self.assertEqual(run.status, "COMPLETED")
        paths = _artifact_paths(self, broken_id)
        paths["metadata"].unlink()
        factory_service.set_run_fields(run.id, status="FINAL_QA")
        _run_final_qa_and_settle(run.id, broken_id, self.settings)
        after = factory_service.get_run(run.id)
        self.assertEqual(after.status, "NEEDS_REVIEW")
        self.assertEqual(after.qa_status, "FAIL")


if __name__ == "__main__":
    unittest.main()
