"""Tests for app/api/v1/endpoints/factory_pipeline.py (Task 18 -- see
docs/features/44-one-click-factory-pipeline.md). Reuses
tests.api.test_batch_render's own _BatchTestCase harness (real file-backed
SQLite shared across Project/Batch/Asset/VideoComposeJob) and extends it
with app.modules.factory's own table + SessionLocal patch, plus a real
EventBus wired into VideoComposerService so factory_pipeline's own
render.job.* subscriptions genuinely fire, exactly like production.
"""

import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.audio_generate import generate_project_audio_master
from app.api.v1.endpoints.beat_generate import generate_beat_plan  # noqa: F401 (patched by name below)
from app.api.v1.endpoints.composition_render import render_beats_for_job
from app.api.v1.endpoints.voice_generate import generate_project_narration
from app.api.v1.endpoints import factory_pipeline as factory_pipeline_module
from app.api.v1.endpoints.factory_pipeline import (
    _execute_pipeline_sync,
    cancel_run,
    continue_batch_factory,
    continue_run,
    create_and_start_run,
    reconcile_factory_runs_on_startup,
    register_factory_event_handlers,
    retry_batch_failed,
    retry_run,
    run_batch_factory,
)
from app.core.config import Settings
from app.core.events import EventBus
from app.db.base import Base
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.batch import service as batch_service
from app.modules.batch.models import Batch, BatchItem
from app.modules.batch.schemas import CreateBatchRequest
from app.modules.beat.models import Project
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType
from app.modules.factory import service as factory_service
from app.modules.factory.models import FactoryCheckpoint, FactoryRun
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob
from app.modules.video_composer.service import VideoComposerService
from tests.api.test_batch_render import FFMPEG_AVAILABLE, _make_solid_image


def _fake_beat_plan(script_text: str, num_beats: int = 3) -> BeatPlan:
    return BeatPlan(
        script_text=script_text,
        beats=[
            Beat(
                id=f"beat_{i:02d}", order=i, type=BeatType.BODY, narration=f"{script_text} part {i}.",
                duration=1.5, visual_hint=None,
            )
            for i in range(1, num_beats + 1)
        ],
    )


class _FactoryTestCase(unittest.TestCase):
    """Independent of _BatchTestCase (not a subclass) -- wires its own real
    EventBus into VideoComposerService so factory_pipeline's render.job.*
    subscriptions genuinely fire in tests, which _BatchTestCase's own
    harness deliberately doesn't need for its own (non-factory) purposes.
    """

    def setUp(self):
        import tempfile

        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

        self.db_path = self.tmp_path / "test.db"
        self.engine = create_engine(f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False, "timeout": 30})
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Batch.__table__, BatchItem.__table__, Project.__table__,
                VideoComposeJob.__table__, VideoComposeClip.__table__, Asset.__table__,
                FactoryRun.__table__, FactoryCheckpoint.__table__,
            ],
        )
        self.TestSessionLocal = sessionmaker(bind=self.engine)

        self.patchers = [
            patch("app.modules.batch.service.SessionLocal", self.TestSessionLocal),
            patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.batch_render.SessionLocal", self.TestSessionLocal),
            patch("app.modules.video_composer.service.SessionLocal", self.TestSessionLocal),
            patch("app.modules.factory.service.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.factory_pipeline.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.voice_generate.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.motion_generate.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.audio_generate.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.package_generate.SessionLocal", self.TestSessionLocal),
        ]
        for p in self.patchers:
            p.start()

        self.settings = Settings(library_dir=str(self.tmp_path), anthropic_api_key="fake-test-key")
        self.event_bus = EventBus()
        register_factory_event_handlers(self.event_bus)
        self.service = VideoComposerService(
            library_dir=self.tmp_path, beat_renderer=render_beats_for_job, event_bus=self.event_bus
        )

        self.image = _make_solid_image(self.tmp_path / "shared.jpg", (200, 40, 40))
        self.asset_id = self._register_image_asset(self.image)

    def tearDown(self):
        self.service.shutdown()
        for p in self.patchers:
            p.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()
        # _cancel_events is a module-global dict keyed by run_id -- each
        # test gets a fresh DB whose ids restart from 1, so a leftover
        # entry from a run that was cancelled before it ever started
        # executing (never hitting _drop_cancel_event's own cleanup) would
        # otherwise leak into the next test and falsely pre-cancel its
        # same-numbered run. Real usage never repeats a run_id across the
        # process lifetime, so this is test-isolation-only cleanup.
        with factory_pipeline_module._cancel_events_lock:
            factory_pipeline_module._cancel_events.clear()
        # Task 20: _batch_pause_events is the exact same kind of
        # module-global, id-keyed leak risk -- a batch left PAUSED (whose
        # pause_event therefore stays .set()) never hits
        # _drop_pause_event's own cleanup, so the same-numbered batch id in
        # the next test's fresh DB would inherit an already-set event and
        # silently no-op every item from the start.
        with factory_pipeline_module._batch_pause_lock:
            factory_pipeline_module._batch_pause_events.clear()

    def _db(self):
        return self.TestSessionLocal()

    def _register_image_asset(self, path: Path, **overrides) -> int:
        db = self._db()
        try:
            asset = AssetService(db).register(
                AssetRegisterIn(filename=path.name, path=str(path), type="image", source="test", **overrides)
            )
            return asset.id
        finally:
            db.close()

    def _create_project(self, name: str, script_text: str = "A short test script.") -> int:
        from app.modules.beat.project_service import create_project
        from app.modules.beat.schemas import ProjectConfig

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            return create_project(name, script_text, ProjectConfig())

    def _get_run(self, run_id: int) -> FactoryRun:
        return factory_service.get_run(run_id)

    # READY_TO_RENDER is included -- it's a real but *transient* state set
    # at the very start of _stage_render, before project_composition_plan/
    # render_composition actually run; a poll landing in that narrow
    # window is still "local stages in flight," not settled yet.
    _LOCAL_STAGES = (
        "PREPARING", "PREPARING_CONTENT", "GENERATING_BEATS", "PREPARING_VISUALS", "ASSIGNING_ASSETS",
        "GENERATING_VOICE", "GENERATING_MOTION", "GENERATING_AUDIO", "GENERATING_CAPTIONS", "QUALITY_CHECK",
        "READY_TO_RENDER",
    )

    def _wait_for_run_settled(self, run_id: int, timeout: float = 30.0) -> FactoryRun:
        """Waits until the background thread has finished the *local*
        stages -- QUEUED (render handed off but no worker running in this
        test), READY_TO_RENDER, NEEDS_REVIEW, FAILED, or CANCELLED all
        count. Use _wait_for_run_terminal instead when the test actually
        started the render worker (self.service.start()) and cares about
        the eventual COMPLETED/FAILED render outcome specifically.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self._get_run(run_id)
            if run.status not in self._LOCAL_STAGES:
                return run
            time.sleep(0.05)
        self.fail("FactoryRun never finished its local stages")

    def _wait_for_run_terminal(self, run_id: int, timeout: float = 30.0) -> FactoryRun:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self._get_run(run_id)
            if run.status in ("COMPLETED", "FAILED", "CANCELLED", "NEEDS_REVIEW"):
                return run
            time.sleep(0.1)
        self.fail("FactoryRun never reached a terminal/paused status")

    def _run_sync(self, project_id: int) -> FactoryRun:
        """Runs the pipeline body directly on the calling thread (no
        background thread, no race to wait out) -- exactly like
        tests.api.test_batch_render's own tests call render_batch()
        synchronously despite production code sometimes threading it.
        """
        run, created = factory_service.create_run(project_id)
        self.assertTrue(created)
        _execute_pipeline_sync(run.id, project_id, self.settings, self.service)
        return self._get_run(run.id)


class StateMachineTests(_FactoryTestCase):
    def test_full_run_reaches_queued_without_a_worker_running(self):
        # Worker deliberately not started here (mirrors test_batch_render's
        # own "worker never started" tests) -- QUEUED is the last state
        # reachable purely through _execute_pipeline_sync's own local
        # stages; RENDERING/COMPLETED require the real worker (covered by
        # EndToEndTests below).
        project_id = self._create_project("State Machine")
        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan", side_effect=lambda key, script: _fake_beat_plan(script)):
            # No beats yet on this project and no asset assigned -- give it
            # one manually-good beat plan up front so it sails through to
            # QUEUED for this specific test (state machine shape, not
            # content quality).
            draft = get_project_draft(project_id)
            plan = BeatPlan(
                script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
                beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hello.", duration=1.0, asset_id=self.asset_id)],
            )
            update_project_beat_plan(project_id, plan)
            run = self._run_sync(project_id)

        self.assertEqual(run.status, "QUEUED")
        self.assertIsNotNone(run.render_job_id)
        self.assertEqual(run.quality_status, "READY")

    def test_render_after_quality_pass_disabled_stops_at_ready_to_render(self):
        # Section 36's own config -- READY_TO_RENDER can be a genuine
        # final state, not just the transient one _stage_render passes
        # through on its way to QUEUED.
        project_id = self._create_project("No Auto Render")
        draft = get_project_draft(project_id)
        config = draft.config.model_copy(deep=True)
        config.factory.render_after_quality_pass = False
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hello.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(project_id, plan)
        run = self._run_sync(project_id)
        self.assertEqual(run.status, "READY_TO_RENDER")
        self.assertIsNone(run.render_job_id)

    def test_no_beats_no_script_fails_at_generating_beats(self):
        project_id = self._create_project("Empty Script", script_text=" ")
        run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "GENERATING_BEATS")
        self.assertEqual(run.error_code, "BEAT_GENERATION_FAILED")

    def test_quality_blocked_fails_at_quality_check(self):
        project_id = self._create_project("Blocked")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hello.", duration=1.0, asset_id=None, visual_hint=None)],
        )
        update_project_beat_plan(project_id, plan)
        run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "QUALITY_CHECK")
        self.assertEqual(run.error_code, "QUALITY_BLOCKED")

    def test_any_active_state_can_be_cancelled(self):
        project_id = self._create_project("Cancel Me")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hello.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(project_id, plan)

        # A real create_and_start_run() call (not the bare create_run() +
        # manual _run_sync used elsewhere in this file) -- cancel_run must
        # cooperate correctly with the background thread it actually races
        # against in production, not a stub run with nothing driving it.
        run = create_and_start_run(project_id, self.settings, self.service)
        cancel_run(run.id, self.service)
        final = self._wait_for_run_terminal(run.id)
        self.assertEqual(final.status, "CANCELLED")


class BeatReuseTests(_FactoryTestCase):
    def test_existing_beats_are_reused_not_regenerated(self):
        project_id = self._create_project("Reuse Beats")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Existing.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(project_id, plan)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            run = self._run_sync(project_id)
            mock_generate.assert_not_called()
        self.assertEqual(run.status, "QUEUED")

    def test_missing_beats_are_generated(self):
        project_id = self._create_project("Generate Beats", script_text="A real script.")
        with patch(
            "app.api.v1.endpoints.factory_pipeline.generate_beat_plan",
            side_effect=lambda key, script: _fake_beat_plan(script, num_beats=1),
        ) as mock_generate:
            run = self._run_sync(project_id)
            mock_generate.assert_called_once()
        # No asset assigned and no visual_hint (the fake generator sets
        # none) -- MISSING_VISUAL_ASSET blocks, but beats themselves exist.
        self.assertIn(run.status, ("FAILED", "NEEDS_REVIEW"))
        draft = get_project_draft(project_id)
        self.assertEqual(len(draft.beats), 1)


class AutoAssignTests(_FactoryTestCase):
    def test_high_confidence_match_is_auto_assigned_and_renders(self):
        asset_path = _make_solid_image(self.tmp_path / "woman_park.jpg", (10, 200, 10))
        asset_id = self._register_image_asset(asset_path, tags=["woman", "park"], width=1080, height=1920)

        project_id = self._create_project("Auto Assign High")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[
                Beat(
                    id="b1", order=1, type=BeatType.BODY, narration="A woman in the park.",
                    duration=1.0, visual_hint="woman park", asset_id=None,
                )
            ],
        )
        update_project_beat_plan(project_id, plan)

        run = self._run_sync(project_id)
        self.assertEqual(run.status, "QUEUED")

        updated_draft = get_project_draft(project_id)
        self.assertEqual(updated_draft.beats[0].asset_id, asset_id)

    def test_manual_assignment_is_never_overwritten(self):
        decoy_path = _make_solid_image(self.tmp_path / "woman_park_decoy.jpg", (10, 200, 10))
        decoy_id = self._register_image_asset(decoy_path, tags=["woman", "park"], width=1080, height=1920)

        project_id = self._create_project("Manual Wins")
        draft = get_project_draft(project_id)
        # asset_id is already manually set to self.asset_id -- a totally
        # unrelated (but valid) asset -- even though a much better keyword
        # match (decoy_id, tagged "woman"/"park") exists in the library.
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[
                Beat(
                    id="b1", order=1, type=BeatType.BODY, narration="A woman in the park.",
                    duration=1.0, visual_hint="woman park", asset_id=self.asset_id,
                )
            ],
        )
        update_project_beat_plan(project_id, plan)
        self.assertNotEqual(self.asset_id, decoy_id)

        self._run_sync(project_id)

        updated_draft = get_project_draft(project_id)
        self.assertEqual(updated_draft.beats[0].asset_id, self.asset_id)  # untouched

    def test_no_candidate_leaves_beat_unassigned_and_blocks(self):
        project_id = self._create_project("No Candidate")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[
                Beat(
                    id="b1", order=1, type=BeatType.BODY, narration="Something.",
                    duration=1.0, visual_hint="a completely unmatched concept zzz", asset_id=None,
                )
            ],
        )
        update_project_beat_plan(project_id, plan)

        run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.error_code, "QUALITY_BLOCKED")


class ReviewResumeTests(_FactoryTestCase):
    def _low_res_asset(self) -> int:
        path = _make_solid_image(self.tmp_path / "low_res.jpg", (40, 40, 200), size=(200, 200))
        return self._register_image_asset(path, tags=["mismatched", "concept"])

    def test_needs_review_pauses_then_continue_resumes_to_render_without_regenerating_beats(self):
        low_res_id = self._low_res_asset()
        project_id = self._create_project("Needs Review Flow")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[
                Beat(
                    id="b1", order=1, type=BeatType.BODY, narration="Real narration text.",
                    duration=1.0, visual_hint="a totally different unrelated wording", asset_id=low_res_id,
                )
            ],
        )
        update_project_beat_plan(project_id, plan)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            run = self._run_sync(project_id)
            mock_generate.assert_not_called()
        self.assertEqual(run.status, "NEEDS_REVIEW")
        self.assertTrue(self._get_run(run.id).requires_human_review)

        # User fixes it: swap in the well-matched, high-res asset, and
        # clear the now-stale visual_hint (a direct manual pick, not a
        # keyword-matched one -- no visual_hint at all reads as HIGH
        # confidence, see quality_gate.compute_asset_confidence's own
        # docstring on why that's correct, not a loophole).
        fixed_draft = get_project_draft(project_id)
        fixed_plan = BeatPlan(
            script_text=fixed_draft.script_text, project_name=fixed_draft.project_name, config=fixed_draft.config,
            beats=[b.model_copy(update={"asset_id": self.asset_id, "visual_hint": None}) for b in fixed_draft.beats],
        )
        update_project_beat_plan(project_id, fixed_plan)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            continue_run(run.id, self.settings, self.service)
            resumed = self._wait_for_run_settled(run.id)
            mock_generate.assert_not_called()

        self.assertEqual(resumed.status, "QUEUED")
        self.assertIsNotNone(resumed.render_job_id)


class RetryTests(_FactoryTestCase):
    def test_asset_match_failure_retry_resumes_from_asset_stage_not_beats(self):
        project_id = self._create_project("Retry Asset Stage")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=None, visual_hint=None)],
        )
        update_project_beat_plan(project_id, plan)

        run = self._run_sync(project_id)
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.failed_stage, "QUALITY_CHECK")

        # Fix: assign an asset directly, then retry -- beats (already
        # present) must not be regenerated.
        fixed_draft = get_project_draft(project_id)
        fixed_plan = BeatPlan(
            script_text=fixed_draft.script_text, project_name=fixed_draft.project_name, config=fixed_draft.config,
            beats=[b.model_copy(update={"asset_id": self.asset_id}) for b in fixed_draft.beats],
        )
        update_project_beat_plan(project_id, fixed_plan)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            retry_run(run.id, self.settings, self.service)
            resumed = self._wait_for_run_settled(run.id)
            mock_generate.assert_not_called()

        self.assertEqual(resumed.status, "QUEUED")

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_render_failure_retry_uses_existing_render_job_retry(self):
        project_id = self._create_project("Retry Render")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(project_id, plan)
        run = self._run_sync(project_id)
        self.assertEqual(run.status, "QUEUED")
        first_job_id = run.render_job_id

        # Simulate a render failure by hand (deterministic, no need to
        # actually break ffmpeg) -- exactly mirrors reconcile's own
        # "job.status == failed" branch.
        factory_service.set_run_fields(
            run.id, status="FAILED", failed_stage="RENDERING", error_code="RENDER_FAILED", error_message="boom",
        )

        with patch("app.modules.video_composer.service.VideoComposerService.retry_job", return_value=999) as mock_retry:
            resumed = retry_run(run.id, self.settings, self.service)
            mock_retry.assert_called_once_with(first_job_id)

        self.assertEqual(resumed.status, "QUEUED")
        self.assertEqual(resumed.render_job_id, 999)


class IdempotencyTests(_FactoryTestCase):
    def test_running_twice_reuses_the_active_run(self):
        project_id = self._create_project("Idempotent Active")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hello.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(project_id, plan)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            run1 = create_and_start_run(project_id, self.settings, self.service)
            run2 = create_and_start_run(project_id, self.settings, self.service)
            self.assertEqual(run1.id, run2.id)
            self._wait_for_run_settled(run1.id)
            mock_generate.assert_not_called()

        db = self._db()
        try:
            count = db.query(FactoryRun).filter(FactoryRun.project_id == project_id).count()
        finally:
            db.close()
        self.assertEqual(count, 1)

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_running_after_completion_does_not_render_twice_unless_forced(self):
        project_id = self._create_project("Idempotent Completed")
        draft = get_project_draft(project_id)
        plan = BeatPlan(
            script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(project_id, plan)

        self.service.start()
        run = self._run_sync(project_id)
        self.assertEqual(run.status, "QUEUED")
        final = self._wait_for_run_terminal(run.id)
        self.assertEqual(final.status, "COMPLETED")

        again = create_and_start_run(project_id, self.settings, self.service)
        self.assertEqual(again.id, final.id)  # same run returned, nothing new started

        db = self._db()
        try:
            job_count = db.query(VideoComposeJob).count()
        finally:
            db.close()
        self.assertEqual(job_count, 1)

        forced = create_and_start_run(project_id, self.settings, self.service, force=True)
        self.assertNotEqual(forced.id, final.id)
        self._wait_for_run_terminal(forced.id)  # let the background thread finish before tearDown tears down its DB


class RecoveryTests(_FactoryTestCase):
    def test_run_stuck_in_a_local_stage_is_marked_interrupted_on_reconcile(self):
        project_id = self._create_project("Interrupted Local")
        run, _created = factory_service.create_run(project_id)
        factory_service.set_run_fields(run.id, status="ASSIGNING_ASSETS")

        reconciled = reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(reconciled, 1)

        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.error_code, "FACTORY_INTERRUPTED")
        self.assertEqual(after.failed_stage, "ASSIGNING_ASSETS")

    def test_rendering_run_reconciles_to_completed_when_job_already_completed(self):
        project_id = self._create_project("Interrupted Render Completed")
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

        reconcile_factory_runs_on_startup(self.settings)
        self.assertEqual(self._get_run(run.id).status, "COMPLETED")

    def test_rendering_run_reconciles_to_failed_when_job_failed(self):
        project_id = self._create_project("Interrupted Render Failed")
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

        reconcile_factory_runs_on_startup(self.settings)
        after = self._get_run(run.id)
        self.assertEqual(after.status, "FAILED")
        self.assertEqual(after.failed_stage, "RENDERING")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class EndToEndTests(_FactoryTestCase):
    def test_one_project_five_beats_local_assets_renders_final_mp4(self):
        assets = [
            self._register_image_asset(
                _make_solid_image(self.tmp_path / f"beat_{i}.jpg", (10 * i, 100, 200 - 10 * i)), width=1080, height=1920
            )
            for i in range(5)
        ]
        project_id = self._create_project("E2E Five Beats")
        draft = get_project_draft(project_id)
        # Varied types -- 5x the same purpose would itself trigger a real,
        # correct LOW_PURPOSE_DIVERSITY warning (see app.modules.quality's
        # own analyze_narrative), which is not what this test is about.
        types = [BeatType.HOOK, BeatType.SETUP, BeatType.BUILD, BeatType.REVEAL, BeatType.ENDING]
        beats = [
            Beat(id=f"b{i+1}", order=i + 1, type=types[i], narration=f"Line {i+1}.", duration=1.0, asset_id=assets[i])
            for i in range(5)
        ]
        plan = BeatPlan(script_text=draft.script_text, project_name=draft.project_name, config=draft.config, beats=beats)
        update_project_beat_plan(project_id, plan)

        self.service.start()
        run = self._run_sync(project_id)
        self.assertEqual(run.status, "QUEUED")
        final = self._wait_for_run_terminal(run.id, timeout=60.0)

        self.assertEqual(final.status, "COMPLETED")
        self.assertEqual(final.quality_status, "READY")

        db = self._db()
        try:
            job = db.get(VideoComposeJob, final.render_job_id)
        finally:
            db.close()
        self.assertEqual(job.status, "completed")
        self.assertTrue(Path(job.output_path).exists())
        report_path = self.tmp_path / ".render" / f"job_{job.id}" / "report.json"
        self.assertTrue(report_path.exists())


class BatchIntegrationTests(_FactoryTestCase):
    def _create_batch(self, name: str, scripts_text: str) -> Batch:
        from app.api.v1.endpoints.batch_render import create_batch

        with patch("app.api.v1.endpoints.batch_render.SessionLocal", self.TestSessionLocal):
            return create_batch(CreateBatchRequest(name=name, template_id="custom", scripts_text=scripts_text), self.settings)

    def test_five_scripts_yield_five_projects_and_five_factory_runs_mixed_outcomes(self):
        scripts = "\n---\n".join(f"Script {i}." for i in range(1, 6))
        batch = self._create_batch("Factory Batch", scripts)
        self.assertEqual(len(batch.items), 5)

        low_res_id = self._register_image_asset(
            _make_solid_image(self.tmp_path / "low_res_batch.jpg", (40, 40, 200), size=(200, 200)),
            tags=["mismatched"],
        )

        def _beats_for(index: int) -> list[Beat]:
            if index in (1, 2):  # READY
                return [Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)]
            if index == 3:  # NEEDS_REVIEW
                return [
                    Beat(
                        id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0,
                        asset_id=low_res_id, visual_hint="totally unrelated wording here",
                    )
                ]
            # index 4, 5 -> BLOCKED (no asset, no visual_hint at all so
            # auto-assign can't even attempt a candidate)
            return [Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=None, visual_hint=None)]

        for item in batch.items:
            draft = get_project_draft(item.project_id)
            plan = BeatPlan(
                script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
                beats=_beats_for(item.index),
            )
            update_project_beat_plan(item.project_id, plan)

        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan") as mock_generate:
            started = run_batch_factory(batch.id, self.settings, self.service)
            mock_generate.assert_not_called()  # every project already had beats -- reused

        self.assertEqual(started, 5)

        db = self._db()
        try:
            runs = db.query(FactoryRun).filter(FactoryRun.project_id.in_([i.project_id for i in batch.items])).all()
        finally:
            db.close()
        statuses = sorted(r.status for r in runs)
        self.assertEqual(statuses, sorted(["QUEUED", "QUEUED", "NEEDS_REVIEW", "FAILED", "FAILED"]))

        # Only the two READY projects actually created a real RenderJob --
        # existing LocalRenderQueue remains the single rendering queue,
        # never bypassed for the NEEDS_REVIEW/BLOCKED ones.
        render_job_ids = [r.render_job_id for r in runs if r.render_job_id is not None]
        self.assertEqual(len(render_job_ids), 2)

    def test_continue_batch_only_touches_needs_review_and_failed(self):
        # Task 20 (see docs/features/46-factory-batch-engine.md): the batch
        # engine now sources eligibility from BatchItem.status (kept in
        # sync with each item's own FactoryRun -- see
        # _sync_batch_item_from_run), not by re-deriving it from FactoryRun
        # directly, so this test sets both together, matching what the
        # real engine itself would have already done. "[Continue Ready]"
        # (NEEDS_REVIEW) and "[Retry Failed]" (FAILED) are now two separate
        # actions/functions (continue_batch_factory / retry_batch_failed).
        batch = self._create_batch("Continue Batch", "One.\n---\nTwo.\n---\nThree.")

        # Item 1: already COMPLETED-equivalent (simulate a finished run) --
        # must be left completely untouched.
        completed_run, _ = factory_service.create_run(batch.items[0].project_id)
        factory_service.set_run_fields(completed_run.id, status="COMPLETED")
        batch_service.set_item_fields(batch.items[0].id, status="COMPLETED")

        # Item 2: NEEDS_REVIEW, now fixed. Continuing this run all the way
        # to QUEUED (asserted below) now requires a real Audio Master
        # (Task 26 -- see docs/features/52-final-composer.md section 59:
        # "Audio Master is required by default"), so Voice + Audio actually
        # run for real here, matching _AudioStageTestCase's own established
        # "exercise the real engine" pattern rather than a fabricated stub.
        draft2 = get_project_draft(batch.items[1].project_id)
        plan2 = BeatPlan(
            script_text=draft2.script_text, project_name=draft2.project_name, config=draft2.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(batch.items[1].project_id, plan2)
        generate_project_narration(batch.items[1].project_id, self.settings)
        generate_project_audio_master(batch.items[1].project_id, self.settings)
        review_run, _ = factory_service.create_run(batch.items[1].project_id)
        factory_service.set_run_fields(review_run.id, status="NEEDS_REVIEW", requires_human_review=True)
        batch_service.set_item_fields(batch.items[1].id, status="NEEDS_REVIEW")

        # Item 3: FAILED at asset stage, now fixed.
        draft3 = get_project_draft(batch.items[2].project_id)
        plan3 = BeatPlan(
            script_text=draft3.script_text, project_name=draft3.project_name, config=draft3.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
        )
        update_project_beat_plan(batch.items[2].project_id, plan3)
        failed_run, _ = factory_service.create_run(batch.items[2].project_id)
        factory_service.set_run_fields(failed_run.id, status="FAILED", failed_stage="QUALITY_CHECK", error_code="QUALITY_BLOCKED")
        batch_service.set_item_fields(batch.items[2].id, status="FAILED")

        continued = continue_batch_factory(batch.id, self.settings, self.service)
        self.assertEqual(continued, 1)
        retried = retry_batch_failed(batch.id, self.settings, self.service)
        self.assertEqual(retried, 1)

        self.assertEqual(self._get_run(completed_run.id).status, "COMPLETED")  # untouched
        self.assertEqual(self._get_run(review_run.id).status, "QUEUED")
        self.assertEqual(self._get_run(failed_run.id).status, "QUEUED")
        self.assertEqual(batch_service.get_batch(batch.id).items[0].status, "COMPLETED")
        self.assertEqual(batch_service.get_batch(batch.id).items[1].status, "RUNNING")
        self.assertEqual(batch_service.get_batch(batch.id).items[2].status, "RUNNING")


if __name__ == "__main__":
    unittest.main()
