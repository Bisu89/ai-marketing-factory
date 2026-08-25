"""Tests for Task 19 -- see docs/features/45-factory-reliability.md.
Reuses tests.api.test_factory_pipeline's own _FactoryTestCase harness (real
file-backed SQLite with FactoryRun + FactoryCheckpoint tables already
wired in there) rather than re-declaring a parallel one.
"""

import time
import unittest
from unittest.mock import patch

from app.api.v1.endpoints.factory_pipeline import (
    _execute_pipeline_sync,
    _is_completed_run_stale,
    _mark_failed,
    create_and_start_run,
    reconcile_factory_runs_on_startup,
    retry_run,
)
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType
from app.modules.factory import service as factory_service
from app.modules.factory.models import FACTORY_MAX_ATTEMPTS, FactoryCheckpoint
from app.modules.factory.schemas import (
    FACTORY_INTERRUPTED,
    FactoryRunOut,
    PERMANENT,
    QUALITY_BLOCKED,
    TRANSIENT,
    USER_ACTION_REQUIRED,
    classify_error,
)
from app.modules.video_composer.models import VideoComposeJob
from tests.api.test_batch_render import FFMPEG_AVAILABLE
from tests.api.test_factory_pipeline import _FactoryTestCase, _fake_beat_plan


def _one_beat_plan(draft, asset_id: int | None, narration: str = "Hi.") -> BeatPlan:
    return BeatPlan(
        script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
        beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration=narration, duration=1.0, asset_id=asset_id)],
    )


class CheckpointPersistenceTests(_FactoryTestCase):
    def test_full_local_run_leaves_a_complete_checkpoint_trail(self):
        project_id = self._create_project("Checkpoint Trail")
        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))

        run = self._run_sync(project_id)
        self.assertEqual(run.status, "QUEUED")

        checkpoints = {c.stage: c for c in factory_service.get_checkpoints(run.id)}
        self.assertEqual(checkpoints["PREPARING"].status, "COMPLETED")
        self.assertEqual(checkpoints["GENERATING_BEATS"].status, "COMPLETED")
        self.assertEqual(checkpoints["GENERATING_BEATS"].checkpoint_metadata["generated"], False)
        self.assertEqual(checkpoints["PREPARING_VISUALS"].status, "SKIPPED")
        self.assertEqual(checkpoints["ASSIGNING_ASSETS"].status, "COMPLETED")
        self.assertEqual(checkpoints["ASSIGNING_ASSETS"].checkpoint_metadata["assigned_count"], 1)
        self.assertEqual(checkpoints["QUALITY_CHECK"].status, "COMPLETED")
        self.assertEqual(checkpoints["QUALITY_CHECK"].checkpoint_metadata["outcome"], "READY")
        self.assertEqual(checkpoints["READY_TO_RENDER"].status, "COMPLETED")
        self.assertEqual(checkpoints["QUEUED"].status, "COMPLETED")
        for checkpoint in checkpoints.values():
            self.assertEqual(checkpoint.attempt, 1)

    def test_blocked_run_leaves_quality_check_checkpoint_failed(self):
        project_id = self._create_project("Blocked Checkpoint")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=None, visual_hint=None)],
        )
        update_project_beat_plan(project_id, plan)

        run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")

        checkpoints = {c.stage: c for c in factory_service.get_checkpoints(run.id)}
        self.assertEqual(checkpoints["QUALITY_CHECK"].status, "FAILED")
        self.assertEqual(checkpoints["QUALITY_CHECK"].error_code, QUALITY_BLOCKED)
        # Upstream stages that genuinely completed stay COMPLETED -- a
        # downstream failure never rewrites an earlier stage's own record.
        self.assertEqual(checkpoints["GENERATING_BEATS"].status, "COMPLETED")
        self.assertEqual(checkpoints["ASSIGNING_ASSETS"].status, "COMPLETED")


class CrashRecoveryPerStageTests(_FactoryTestCase):
    """Section 18/48/54: simulate the process dying while stuck in each
    major stage, then verify reconcile settles both FactoryRun and its
    matching FactoryCheckpoint without regenerating anything upstream.
    """

    def _stuck_run(self, project_id: int, stage: str) -> int:
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status=stage)
        factory_service.start_checkpoint(run.id, stage)
        return run.id

    def test_interrupted_during_generating_beats(self):
        project_id = self._create_project("Interrupted Beats")
        run_id = self._stuck_run(project_id, "GENERATING_BEATS")

        reconciled = reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)

        run = self._get_run(run_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "GENERATING_BEATS")
        self.assertEqual(run.error_code, FACTORY_INTERRUPTED)

        checkpoint = factory_service.get_checkpoints(run_id)[0]
        self.assertEqual(checkpoint.stage, "GENERATING_BEATS")
        self.assertEqual(checkpoint.status, "FAILED")
        self.assertEqual(checkpoint.error_code, FACTORY_INTERRUPTED)

        # Retry must not regenerate Beats -- none existed before the crash,
        # so generate_beat_plan is expected to be called exactly once here,
        # proving the retry path itself is exercised (not skipped) while
        # nothing upstream is silently duplicated.
        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))
        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            retry_run(run_id, self.settings, self.service)
            resumed = self._wait_for_run_settled(run_id)
            mock_generate.assert_not_called()  # beats already exist now -- reused, not regenerated
        self.assertEqual(resumed.status, "QUEUED")

    def test_interrupted_during_assigning_assets_does_not_regenerate_beats(self):
        project_id = self._create_project("Interrupted Visuals")
        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))
        run_id = self._stuck_run(project_id, "ASSIGNING_ASSETS")

        reconcile_factory_runs_on_startup(self.settings)
        run = self._get_run(run_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "ASSIGNING_ASSETS")

        checkpoint = next(c for c in factory_service.get_checkpoints(run_id) if c.stage == "ASSIGNING_ASSETS")
        self.assertEqual(checkpoint.status, "FAILED")

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            retry_run(run_id, self.settings, self.service)
            resumed = self._wait_for_run_settled(run_id)
            mock_generate.assert_not_called()
        self.assertEqual(resumed.status, "QUEUED")
        # Retrying the same stage re-enters its checkpoint row (attempt+1),
        # not a second row.
        checkpoints = factory_service.get_checkpoints(run_id)
        assign_checkpoints = [c for c in checkpoints if c.stage == "ASSIGNING_ASSETS"]
        self.assertEqual(len(assign_checkpoints), 1)
        self.assertEqual(assign_checkpoints[0].attempt, 2)

    def test_interrupted_during_quality_check(self):
        project_id = self._create_project("Interrupted Quality")
        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))
        run_id = self._stuck_run(project_id, "QUALITY_CHECK")

        reconcile_factory_runs_on_startup(self.settings)
        run = self._get_run(run_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "QUALITY_CHECK")
        checkpoint = next(c for c in factory_service.get_checkpoints(run_id) if c.stage == "QUALITY_CHECK")
        self.assertEqual(checkpoint.status, "FAILED")

    def test_interrupted_while_queued_with_no_render_job_yet(self):
        project_id = self._create_project("Interrupted Queue")
        run_id = self._stuck_run(project_id, "QUEUED")
        # No render_job_id set -- crash happened before render_composition()
        # ever returned a job id (see _stage_render's own ordering).

        reconcile_factory_runs_on_startup(self.settings)
        run = self._get_run(run_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "QUEUED")

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_interrupted_during_rendering_with_job_still_running_is_recoverable(self):
        project_id = self._create_project("Interrupted Render")
        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))

        run = self._run_sync(project_id)
        self.assertEqual(run.status, "QUEUED")
        factory_service.set_run_fields(run.id, status="RENDERING")
        factory_service.start_checkpoint(run.id, "RENDERING")

        # The job itself is still "queued" (never started, worker not
        # running in this test) -- reconcile must not claim RUNNING forever
        # (section 46) even though it isn't "failed" either.
        reconcile_factory_runs_on_startup(self.settings)
        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.error_code, FACTORY_INTERRUPTED)
        checkpoint = next(c for c in factory_service.get_checkpoints(run.id) if c.stage == "RENDERING")
        self.assertEqual(checkpoint.status, "FAILED")

        # Retry must delegate to the existing render queue's retry_job, not
        # regenerate Beats/re-run Quality (those already passed).
        with patch("app.modules.video_composer.service.VideoComposerService.retry_job", return_value=999) as mock_retry:
            resumed = retry_run(run.id, self.settings, self.service)
            mock_retry.assert_called_once()
        self.assertEqual(resumed.status, "QUEUED")
        self.assertEqual(resumed.render_job_id, 999)


class ReconciliationIdempotencyTests(_FactoryTestCase):
    def test_reconciling_twice_does_not_duplicate_checkpoints_or_change_terminal_state(self):
        project_id = self._create_project("Reconcile Twice")
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="ASSIGNING_ASSETS")
        factory_service.start_checkpoint(run.id, "ASSIGNING_ASSETS")

        reconcile_factory_runs_on_startup(self.settings)
        first = self._get_run(run.id)
        first_checkpoints = factory_service.get_checkpoints(run.id)

        # A second reconciliation pass (e.g. a second startup, or a bug
        # calling it twice) must not find this run again -- it is no longer
        # in an active status -- so nothing changes.
        reconciled_again = reconcile_factory_runs_on_startup(self.settings)
        second = self._get_run(run.id)
        second_checkpoints = factory_service.get_checkpoints(run.id)

        self.assertEqual(first.status, second.status)
        self.assertEqual(first.updated_at, second.updated_at)
        self.assertEqual(len(first_checkpoints), len(second_checkpoints))
        # This specific run wasn't reconciled the second time (already
        # terminal) -- reconciled_again counts whatever *other* active runs
        # existed, none here.
        self.assertEqual(reconciled_again, 0)

    def test_no_duplicate_checkpoint_rows_across_retries_of_the_same_stage(self):
        project_id = self._create_project("No Duplicate Checkpoints")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=None, visual_hint=None)],
        )
        update_project_beat_plan(project_id, plan)

        run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")  # QUALITY_BLOCKED, no asset

        fixed_draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(fixed_draft, self.asset_id))
        retry_run(run.id, self.settings, self.service)
        self._wait_for_run_settled(run.id)

        checkpoints = factory_service.get_checkpoints(run.id)
        stages = [c.stage for c in checkpoints]
        self.assertEqual(len(stages), len(set(stages)), f"duplicate checkpoint rows: {stages}")


class InvalidationTests(_FactoryTestCase):
    """Section 14/29-34: a COMPLETED run's own quality/render result must
    not be trusted once the project is edited afterward.
    """

    def test_fresh_completed_run_is_not_stale(self):
        project_id = self._create_project("Not Stale")
        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))
        run = self._run_sync(project_id)
        factory_service.set_run_fields(run.id, status="COMPLETED", completed_at=factory_service._utcnow())
        completed = self._get_run(run.id)
        self.assertFalse(_is_completed_run_stale(completed))

    def test_editing_project_after_completion_marks_the_run_stale(self):
        project_id = self._create_project("Now Stale")
        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))
        run = self._run_sync(project_id)
        factory_service.set_run_fields(run.id, status="COMPLETED", completed_at=factory_service._utcnow())
        completed = self._get_run(run.id)

        # A tiny real delay -- SQLite's own DateTime round-trip precision
        # (Task 19's own finding) can otherwise land completed_at and the
        # edit's updated_at in the same rounded instant on a fast/loaded
        # test run, which would make the ">" comparison this test is
        # actually about spuriously false.
        time.sleep(0.01)

        # A later, independent edit (real content change, not a no-op
        # rewrite of the same values -- Project.updated_at only bumps when
        # the ORM actually detects a diff) bumps Project.updated_at past
        # this run's own completed_at.
        edited_draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(edited_draft, self.asset_id, narration="Edited narration."))

        self.assertTrue(_is_completed_run_stale(completed))

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_create_and_start_run_starts_a_fresh_run_for_a_stale_completed_project(self):
        project_id = self._create_project("Stale Reproduce")
        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))

        self.service.start()
        first = create_and_start_run(project_id, self.settings, self.service)
        first_final = self._wait_for_run_terminal(first.id)
        self.assertEqual(first_final.status, "COMPLETED")

        # Edit the project post-completion (new narration text) -- the
        # previous render no longer reflects current project state.
        edited_draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(edited_draft, self.asset_id, narration="Edited narration."))

        second = create_and_start_run(project_id, self.settings, self.service)
        self.assertNotEqual(second.id, first_final.id)
        self._wait_for_run_terminal(second.id)


class RetryAttemptAndClassificationTests(_FactoryTestCase):
    def test_retry_increments_attempt(self):
        project_id = self._create_project("Attempt Count")
        run, _created = factory_service.create_run(project_id)
        self.assertEqual(run.attempt, 1)
        _execute_pipeline_sync(run.id, project_id, self.settings, self.service)
        failed = self._get_run(run.id)
        self.assertEqual(failed.status, "FAILED")
        self.assertEqual(failed.attempt, 1)

        draft = get_project_draft(project_id)
        update_project_beat_plan(project_id, _one_beat_plan(draft, self.asset_id))
        retry_run(run.id, self.settings, self.service)
        resumed = self._wait_for_run_settled(run.id)
        self.assertEqual(resumed.attempt, 2)

    def test_max_attempts_reached_is_informational_not_blocking(self):
        project_id = self._create_project("Max Attempts")
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, attempt=FACTORY_MAX_ATTEMPTS)
        _mark_failed(run.id, "GENERATING_BEATS", "BEAT_GENERATION_FAILED", "boom")

        out = FactoryRunOut.model_validate(self._get_run(run.id))
        self.assertTrue(out.max_attempts_reached)

        # Manual retry must still succeed past the "soft" max -- this app
        # has no automatic retry loop to actually cap (see
        # FACTORY_MAX_ATTEMPTS' own docstring).
        with patch(
            "app.api.v1.endpoints.factory_pipeline.generate_beat_plan",
            side_effect=lambda key, script, **_: _fake_beat_plan(script, 1),
        ):
            retry_run(run.id, self.settings, self.service)
            resumed = self._wait_for_run_settled(run.id)
        self.assertNotEqual(resumed.status, "PENDING")  # it actually ran, wasn't blocked

    def test_error_classification_table(self):
        self.assertEqual(classify_error(QUALITY_BLOCKED), USER_ACTION_REQUIRED)
        self.assertEqual(classify_error(FACTORY_INTERRUPTED), TRANSIENT)
        self.assertEqual(classify_error("RENDER_INTERRUPTED"), TRANSIENT)
        self.assertEqual(classify_error("MISSING_ASSET"), USER_ACTION_REQUIRED)
        self.assertEqual(classify_error("FFMPEG_NOT_FOUND"), PERMANENT)
        self.assertIsNone(classify_error(None))
        self.assertEqual(classify_error("SOME_FUTURE_UNMAPPED_CODE"), PERMANENT)

    def test_factory_run_out_exposes_error_classification(self):
        project_id = self._create_project("Classification Exposed")
        run, _created = factory_service.create_run(project_id)
        _mark_failed(run.id, "QUALITY_CHECK", QUALITY_BLOCKED, "blocked")
        out = FactoryRunOut.model_validate(self._get_run(run.id))
        self.assertEqual(out.error_classification, USER_ACTION_REQUIRED)


class RenderReconciliationCheckpointTests(_FactoryTestCase):
    def test_completed_render_settles_queued_and_rendering_checkpoints(self):
        project_id = self._create_project("Reconcile Completed Checkpoints")
        db = self._db()
        try:
            job = VideoComposeJob(title="x", script_text="x", status="completed")
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
        finally:
            db.close()

        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="RENDERING", render_job_id=job_id)
        factory_service.start_checkpoint(run.id, "RENDERING")

        reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(self._get_run(run.id).status, "COMPLETED")

        checkpoints = {c.stage: c for c in factory_service.get_checkpoints(run.id)}
        self.assertEqual(checkpoints["QUEUED"].status, "COMPLETED")
        self.assertEqual(checkpoints["RENDERING"].status, "COMPLETED")

    def test_failed_render_settles_rendering_checkpoint_as_failed(self):
        project_id = self._create_project("Reconcile Failed Checkpoints")
        db = self._db()
        try:
            job = VideoComposeJob(title="x", script_text="x", status="failed", error_message="disk full")
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
        finally:
            db.close()

        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="RENDERING", render_job_id=job_id)
        factory_service.start_checkpoint(run.id, "RENDERING")

        reconcile_factory_runs_on_startup(self.settings)
        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")

        checkpoints = {c.stage: c for c in factory_service.get_checkpoints(run.id)}
        self.assertEqual(checkpoints["RENDERING"].status, "FAILED")
        self.assertEqual(checkpoints["QUEUED"].status, "COMPLETED")  # it *was* queued successfully


if __name__ == "__main__":
    unittest.main()
