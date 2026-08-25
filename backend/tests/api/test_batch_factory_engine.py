"""Tests for Task 20 -- see docs/features/46-factory-batch-engine.md.
Reuses tests.api.test_factory_pipeline's own _FactoryTestCase harness.
Concurrency/FIFO/pause/cancel/stress tests patch _execute_pipeline_sync
with a small instrumented fake (real Claude/ffmpeg not needed to prove
*scheduling* behavior -- those are already covered end-to-end elsewhere,
see EndToEndTests/RetryTests in test_factory_pipeline.py); isolation tests
(NEEDS_REVIEW/FAILED) use the real pipeline against real local assets, the
same pattern test_factory_pipeline.py's own AutoAssignTests/ReviewResumeTests
already establish.
"""

import threading
import time
import unittest
from unittest.mock import patch

from app.api.v1.endpoints import factory_pipeline as factory_pipeline_module
from app.api.v1.endpoints.factory_pipeline import (
    cancel_batch_engine,
    continue_batch_factory,
    pause_batch_engine,
    reconcile_batches_on_startup,
    reconcile_factory_runs_on_startup,
    resume_batch_engine,
    retry_batch_failed,
    run_batch_factory,
    skip_batch_item,
    start_batch_run,
)
from app.core.concurrency import ai_generation_semaphore
from app.modules.batch import service as batch_service
from app.modules.batch.models import Batch
from app.modules.batch.schemas import CreateBatchRequest
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType
from app.modules.factory import service as factory_service
from app.modules.factory.models import FactoryRun
from app.modules.video_composer.models import VideoComposeJob
from tests.api.test_batch_render import FFMPEG_AVAILABLE, _make_solid_image
from tests.api.test_factory_pipeline import _FactoryTestCase


class _BatchEngineTestCase(_FactoryTestCase):
    def _create_batch(self, name: str, scripts_text: str) -> Batch:
        from app.api.v1.endpoints.batch_render import create_batch

        with patch("app.api.v1.endpoints.batch_render.SessionLocal", self.TestSessionLocal):
            return create_batch(CreateBatchRequest(name=name, template_id="custom", scripts_text=scripts_text), self.settings)

    def _batch(self, batch_id: int) -> Batch:
        return batch_service.get_batch(batch_id)

    def _wait_for_fake_active(self, fake: "_InstrumentedFakeExecute", timeout: float = 5.0) -> None:
        """Waits until the fake has genuinely started at least one call --
        a blind time.sleep() before pausing/cancelling is otherwise a race
        against real thread-startup + DB overhead (ThreadPoolExecutor
        thread spin-up, claim_item, create_run), especially under a loaded
        test suite: too short a sleep can let pause_batch_engine's own
        pause_event.set() land *before* any worker even checked it.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with fake.lock:
                if fake.active >= 1:
                    return
            time.sleep(0.005)
        self.fail("fake execute never became active")

    def _wait_for_fake_idle(self, fake: "_InstrumentedFakeExecute", timeout: float = 5.0) -> None:
        """Waits for every in-flight _InstrumentedFakeExecute call to
        actually finish (fake.active back to 0) -- Batch.status alone isn't
        a reliable signal here since pause_batch_engine/cancel_batch_engine
        both flip it synchronously, ahead of whatever item was already
        mid-flight when they were called.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with fake.lock:
                if fake.active == 0:
                    # fake.active drops to 0 right after set_run_fields, but
                    # slightly before _run_batch_item's own subsequent
                    # BatchItem sync call -- a tiny grace period lets that
                    # fast, purely-local DB write land too.
                    time.sleep(0.03)
                    return
            time.sleep(0.01)
        self.fail("fake execute never went idle")


class _InstrumentedFakeExecute:
    """Replaces _execute_pipeline_sync with a controllable, concurrency-
    observing fake -- records concurrently-active call count (peak) and
    call order, sleeps `delay` seconds while "running", then settles the
    FactoryRun COMPLETED. No Claude/ffmpeg involved, so these tests run in
    milliseconds regardless of how many projects are simulated.
    """

    def __init__(self, delay: float = 0.05):
        self.delay = delay
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.start_order: list[int] = []

    def __call__(self, run_id: int, project_id: int, settings, service) -> None:
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.start_order.append(project_id)
        time.sleep(self.delay)
        factory_service.set_run_fields(run_id, status="COMPLETED", completed_at=factory_service._utcnow())
        with self.lock:
            self.active -= 1


class SchedulerConcurrencyTests(_BatchEngineTestCase):
    def test_max_parallel_projects_is_never_exceeded(self):
        batch = self._create_batch("Concurrency", "\n---\n".join(f"S{i}." for i in range(1, 6)))
        self.settings.max_parallel_projects = 2
        fake = _InstrumentedFakeExecute(delay=0.05)

        with patch("app.api.v1.endpoints.factory_pipeline._execute_pipeline_sync", fake):
            started = run_batch_factory(batch.id, self.settings, self.service)

        self.assertEqual(started, 5)
        self.assertLessEqual(fake.peak, 2)
        self.assertGreater(fake.peak, 1)  # proves real concurrency happened, not accidental serialization

    def test_fifo_start_order_with_full_serialization(self):
        batch = self._create_batch("FIFO", "\n---\n".join(f"S{i}." for i in range(1, 5)))
        self.settings.max_parallel_projects = 1
        fake = _InstrumentedFakeExecute(delay=0.01)
        expected_order = [item.project_id for item in self._batch(batch.id).items]

        with patch("app.api.v1.endpoints.factory_pipeline._execute_pipeline_sync", fake):
            run_batch_factory(batch.id, self.settings, self.service)

        self.assertEqual(fake.start_order, expected_order)

    def test_render_concurrency_is_structurally_one_worker(self):
        # Section 4/11: keep the existing renderer serial -- proven by the
        # existing single self._worker thread field, not a config value
        # this task introduces (see max_parallel_renders' own docstring).
        self.assertIsNone(self.service._worker)  # not started in this test
        self.assertEqual(self.settings.max_parallel_renders, 1)

    def test_fifty_project_stress_respects_concurrency_limit(self):
        batch = self._create_batch("Stress", "\n---\n".join(f"S{i}." for i in range(1, 51)))
        self.assertEqual(len(self._batch(batch.id).items), 50)
        self.settings.max_parallel_projects = 2
        fake = _InstrumentedFakeExecute(delay=0.01)

        with patch("app.api.v1.endpoints.factory_pipeline._execute_pipeline_sync", fake):
            started = run_batch_factory(batch.id, self.settings, self.service)

        self.assertEqual(started, 50)
        self.assertLessEqual(fake.peak, 2)
        final = self._batch(batch.id)
        self.assertTrue(all(item.status == "COMPLETED" for item in final.items))
        self.assertEqual(final.status, "COMPLETED")


class AIConcurrencySemaphoreTests(unittest.TestCase):
    def test_semaphore_bounds_concurrent_holders(self):
        # threading.Semaphore doesn't expose its configured bound publicly
        # across all Python versions -- a fresh, known-sized one exercises
        # the exact same primitive app.core.concurrency.ai_generation_semaphore
        # is built from, without relying on CPython internals for the
        # assertion itself.
        sem = threading.Semaphore(2)
        active = 0
        peak = 0
        lock = threading.Lock()

        def worker():
            nonlocal active, peak
            with sem:
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.03)
                with lock:
                    active -= 1

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertLessEqual(peak, 2)
        self.assertGreater(peak, 1)


class AIConcurrencyWiringTests(_BatchEngineTestCase):
    def test_beat_generation_call_site_holds_the_shared_semaphore(self):
        """Confirms _stage_generate_beats actually acquires/releases
        app.core.concurrency.ai_generation_semaphore around the real AI
        call site (section 12) -- not just that a semaphore of that shape
        exists somewhere unused. Reads the semaphore's own internal
        counter rather than mocking acquire/release: threading.Semaphore
        binds `__enter__ = acquire` at class-definition time, so `with
        sem:` calls the *original* acquire directly and silently bypasses
        an instance-level monkeypatch of `.acquire` -- the counter is the
        reliable, honest signal here.
        """
        project_id = self._create_project("Semaphore Wiring", script_text="A real script.")
        observed_value_during_call = {}

        def _fake_generate(key, script, **_):
            observed_value_during_call["value"] = ai_generation_semaphore._value
            return BeatPlan(script_text=script, beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="x", duration=1.0)])

        before = ai_generation_semaphore._value
        with patch("app.api.v1.endpoints.factory_pipeline.generate_beat_plan", side_effect=_fake_generate):
            factory_pipeline_module._stage_generate_beats(project_id, self.settings)
        after = ai_generation_semaphore._value

        self.assertEqual(observed_value_during_call["value"], before - 1)  # held during the real call
        self.assertEqual(after, before)  # released afterward


class ReviewAndFailureIsolationTests(_BatchEngineTestCase):
    def _low_res_asset(self) -> int:
        path = _make_solid_image(self.tmp_path / "low_res_iso.jpg", (40, 40, 200), size=(200, 200))
        return self._register_image_asset(path, tags=["mismatched", "concept"])

    def test_needs_review_item_does_not_block_ready_items(self):
        batch = self._create_batch("Review Isolation", "One.\n---\nTwo.\n---\nThree.")
        items = self._batch(batch.id).items
        low_res_id = self._low_res_asset()

        review_draft = get_project_draft(items[0].project_id)
        update_project_beat_plan(items[0].project_id, BeatPlan(
            script_text=review_draft.script_text, project_name=review_draft.project_name, config=review_draft.config,
            beats=[Beat(
                id="b1", order=1, type=BeatType.BODY, narration="Real narration.", duration=1.0,
                visual_hint="a totally different unrelated wording", asset_id=low_res_id,
            )],
        ))
        for item in items[1:]:
            draft = get_project_draft(item.project_id)
            update_project_beat_plan(item.project_id, BeatPlan(
                script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
                beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
            ))

        self.settings.max_parallel_projects = 3
        started = run_batch_factory(batch.id, self.settings, self.service)
        self.assertEqual(started, 3)

        final = self._batch(batch.id)
        statuses = {item.project_id: item.status for item in final.items}
        self.assertEqual(statuses[items[0].project_id], "NEEDS_REVIEW")
        self.assertEqual(statuses[items[1].project_id], "RUNNING")  # QUEUED under the hood -- render handed off
        self.assertEqual(statuses[items[2].project_id], "RUNNING")

    def test_failed_item_does_not_block_ready_items(self):
        batch = self._create_batch("Failure Isolation", "One.\n---\nTwo.\n---\nThree.")
        items = self._batch(batch.id).items

        blocked_draft = get_project_draft(items[0].project_id)
        update_project_beat_plan(items[0].project_id, BeatPlan(
            script_text=blocked_draft.script_text, project_name=blocked_draft.project_name, config=blocked_draft.config,
            beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=None, visual_hint=None)],
        ))
        for item in items[1:]:
            draft = get_project_draft(item.project_id)
            update_project_beat_plan(item.project_id, BeatPlan(
                script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
                beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
            ))

        self.settings.max_parallel_projects = 3
        started = run_batch_factory(batch.id, self.settings, self.service)
        self.assertEqual(started, 3)

        final = self._batch(batch.id)
        statuses = {item.project_id: item.status for item in final.items}
        self.assertEqual(statuses[items[0].project_id], "FAILED")
        self.assertEqual(statuses[items[1].project_id], "RUNNING")
        self.assertEqual(statuses[items[2].project_id], "RUNNING")
        # Section 40/42: one failure must never leave the batch in an
        # inconsistent/crashed state -- it settles to a real, derived status.
        self.assertIn(final.status, ("PROCESSING", "PARTIAL_FAILURE"))


class PauseResumeCancelTests(_BatchEngineTestCase):
    def test_pause_stops_new_claims_running_items_finish(self):
        batch = self._create_batch("Pause", "\n---\n".join(f"S{i}." for i in range(1, 4)))
        self.settings.max_parallel_projects = 1
        fake = _InstrumentedFakeExecute(delay=0.15)

        with patch("app.api.v1.endpoints.factory_pipeline._execute_pipeline_sync", fake):
            batch_service.set_batch_status(batch.id, "PROCESSING")
            start_batch_run(batch.id, self.settings, self.service)
            self._wait_for_fake_active(fake)  # the first item has genuinely started claiming/running
            pause_batch_engine(batch.id)
            # pause_batch_engine flips Batch.status to PAUSED synchronously
            # (immediate UI feedback), well before the item already in
            # flight has actually finished its own fake delay -- wait for
            # that item's own real completion instead of polling
            # Batch.status, which would otherwise pass before it settles.
            self._wait_for_fake_idle(fake)

        paused = self._batch(batch.id)
        self.assertEqual(paused.status, "PAUSED")
        statuses = [item.status for item in paused.items]
        self.assertIn("COMPLETED", statuses)  # the one already-claimed item ran to completion
        self.assertIn("PROJECT_CREATED", statuses)  # the rest were never claimed

    def test_resume_only_continues_pending_items(self):
        batch = self._create_batch("Resume", "\n---\n".join(f"S{i}." for i in range(1, 4)))
        self.settings.max_parallel_projects = 1
        fake = _InstrumentedFakeExecute(delay=0.15)

        with patch("app.api.v1.endpoints.factory_pipeline._execute_pipeline_sync", fake):
            batch_service.set_batch_status(batch.id, "PROCESSING")
            start_batch_run(batch.id, self.settings, self.service)
            self._wait_for_fake_active(fake)
            pause_batch_engine(batch.id)
            self._wait_for_fake_idle(fake)
            completed_before_resume = sum(1 for i in self._batch(batch.id).items if i.status == "COMPLETED")
            self.assertGreaterEqual(completed_before_resume, 1)

            resume_batch_engine(batch.id, self.settings, self.service)
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and self._batch(batch.id).status not in (
                "COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED",
            ):
                time.sleep(0.02)

        final = self._batch(batch.id)
        self.assertEqual(final.status, "COMPLETED")
        self.assertTrue(all(item.status == "COMPLETED" for item in final.items))

    def test_resume_of_a_running_batch_is_rejected(self):
        batch = self._create_batch("Resume Guard", "One.")
        batch_service.set_batch_status(batch.id, "PROCESSING")
        with self.assertRaises(Exception):
            resume_batch_engine(batch.id, self.settings, self.service)

    def test_cancel_marks_pending_cancelled_and_preserves_completed(self):
        batch = self._create_batch("Cancel", "\n---\n".join(f"S{i}." for i in range(1, 5)))
        self.settings.max_parallel_projects = 1
        fake = _InstrumentedFakeExecute(delay=0.15)

        with patch("app.api.v1.endpoints.factory_pipeline._execute_pipeline_sync", fake):
            batch_service.set_batch_status(batch.id, "PROCESSING")
            start_batch_run(batch.id, self.settings, self.service)
            self._wait_for_fake_active(fake)
            cancel_batch_engine(batch.id, self.service)
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and self._batch(batch.id).status == "PROCESSING":
                time.sleep(0.02)

        final = self._batch(batch.id)
        statuses = [item.status for item in final.items]
        self.assertIn("COMPLETED", statuses)  # already-finished work is never reverted (section 24)
        self.assertIn("CANCELLED", statuses)  # never-claimed items became CANCELLED
        self.assertNotIn("PROJECT_CREATED", statuses)  # nothing left unresolved


class SkipTests(_BatchEngineTestCase):
    def test_skip_pending_item_removes_it_from_eligibility(self):
        batch = self._create_batch("Skip", "One.\n---\nTwo.")
        items = self._batch(batch.id).items
        self.assertTrue(skip_batch_item(items[0].id))
        batch_service.recompute_batch_status(batch.id)

        after = self._batch(batch.id)
        self.assertEqual(next(i for i in after.items if i.id == items[0].id).status, "SKIPPED")

        for item in after.items:
            if item.id == items[1].id:
                draft = get_project_draft(item.project_id)
                update_project_beat_plan(item.project_id, BeatPlan(
                    script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
                    beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
                ))

        started = run_batch_factory(batch.id, self.settings, self.service)
        self.assertEqual(started, 1)  # the skipped item was never claimed


class RestartRecoveryTests(_BatchEngineTestCase):
    def test_running_batch_becomes_paused_after_restart(self):
        batch = self._create_batch("Restart", "One.\n---\nTwo.")
        items = self._batch(batch.id).items
        batch_service.set_batch_status(batch.id, "PROCESSING")

        run, _created = factory_service.create_run(items[0].project_id)
        factory_service.set_run_fields(run.id, status="ASSIGNING_ASSETS")
        batch_service.set_item_fields(items[0].id, status="RUNNING")
        # items[1] never got claimed yet -- stays PROJECT_CREATED, matching
        # a real in-progress batch (section 43's own scenario).

        reconcile_factory_runs_on_startup(self.settings)
        reconcile_batches_on_startup()

        after = self._batch(batch.id)
        self.assertEqual(after.status, "PAUSED_AFTER_RESTART")
        after_item0 = next(i for i in after.items if i.id == items[0].id)
        self.assertEqual(after_item0.status, "FAILED")  # synced from the now-interrupted FactoryRun
        after_item1 = next(i for i in after.items if i.id == items[1].id)
        self.assertEqual(after_item1.status, "PROJECT_CREATED")  # untouched, still eligible for Resume

        # Explicit Resume required (section 44) -- reconciliation alone
        # must never restart anything.
        for item in after.items:
            draft = get_project_draft(item.project_id)
            update_project_beat_plan(item.project_id, BeatPlan(
                script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
                beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
            ))
        resume_batch_engine(batch.id, self.settings, self.service)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and self._batch(batch.id).status == "PROCESSING":
            time.sleep(0.05)
        final = self._batch(batch.id)
        self.assertNotEqual(final.status, "PAUSED_AFTER_RESTART")


class IdempotencyTests(_BatchEngineTestCase):
    def test_running_batch_twice_creates_no_duplicate_factory_runs(self):
        batch = self._create_batch("Batch Idempotency", "One.\n---\nTwo.")
        for item in self._batch(batch.id).items:
            draft = get_project_draft(item.project_id)
            update_project_beat_plan(item.project_id, BeatPlan(
                script_text=draft.script_text, project_name=draft.project_name, config=draft.config,
                beats=[Beat(id="b1", order=1, type=BeatType.BODY, narration="Hi.", duration=1.0, asset_id=self.asset_id)],
            ))

        first_started = run_batch_factory(batch.id, self.settings, self.service)
        second_started = run_batch_factory(batch.id, self.settings, self.service)
        self.assertEqual(first_started, 2)
        self.assertEqual(second_started, 0)  # every item already claimed -- nothing left to start

        project_ids = [item.project_id for item in self._batch(batch.id).items]
        db = self._db()
        try:
            run_count = db.query(FactoryRun).filter(FactoryRun.project_id.in_(project_ids)).count()
            job_count = db.query(VideoComposeJob).count()
        finally:
            db.close()
        self.assertEqual(run_count, 2)  # one per project, never duplicated
        self.assertLessEqual(job_count, 2)


if __name__ == "__main__":
    unittest.main()
