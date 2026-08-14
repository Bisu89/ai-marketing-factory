"""Tests for the Task 11 render-job hardening work (see
docs/features/38-render-job-hardening.md): the QUEUED/RUNNING/COMPLETED/
FAILED/CANCELLED state machine, the local FIFO/single-concurrency queue,
cancellation (queued and running), crash recovery, and retry. Queue/
cancellation tests mock the beat-rendering pipeline (a fake, controllable
`beat_renderer`) rather than using long real ffmpeg renders, per this
task's own "mock the pipeline where appropriate" instruction -- real,
unmocked end-to-end rendering is already covered by
FullLocalEndToEndPipelineTests (tests/api/test_composition_render.py) and
GoldenSampleRenderAcceptanceTest (tests/examples/test_golden_sample_render.py).
"""

import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.composition_render import render_beats_for_job
from app.core import render_errors
from app.core.exceptions import RenderCancelled, ValidationError
from app.db.base import Base
from app.modules.video_composer.models import COARSE_STATUS, VideoComposeClip, VideoComposeJob
from app.modules.video_composer.service import VideoComposerService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

_WAIT_TIMEOUT_SEC = 5.0
_POLL_SEC = 0.02


class _JobLifecycleTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine, tables=[VideoComposeJob.__table__, VideoComposeClip.__table__])
        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.session_patcher = patch("app.modules.video_composer.service.SessionLocal", self.TestSessionLocal)
        self.session_patcher.start()

        self.execution_order: list[str] = []

    def tearDown(self):
        self.session_patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _get_job(self, job_id: int) -> VideoComposeJob:
        db = self.TestSessionLocal()
        try:
            return db.query(VideoComposeJob).filter(VideoComposeJob.id == job_id).first()
        finally:
            db.close()

    def _make_job(self, label: str, *, slow: bool = False) -> int:
        return self.service.create_job(
            title=label, script_text="", voice="en-US-GuyNeural", music_volume=0.15,
            transition_duration=0.3, burn_subtitles=False, requested_output_dir=None,
            composition_request_json={"label": label, "slow": slow},
        )

    def _wait_until(self, predicate, timeout: float = _WAIT_TIMEOUT_SEC) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(_POLL_SEC)
        self.fail("Timed out waiting for condition")

    def _wait_terminal(self, job_id: int, timeout: float = _WAIT_TIMEOUT_SEC) -> str:
        self._wait_until(lambda: self._get_job(job_id).status in ("completed", "failed", "cancelled"), timeout)
        return self._get_job(job_id).status


class FakeBeatRenderer:
    """A controllable stand-in for render_beats_for_job: records call order,
    optionally blocks (checking `is_cancelled` in a tight loop, like a real
    long-running render would between beats) until told to release, and
    always returns an empty clip list -- the real _run_job main body then
    fails the job with "no clips" immediately after, which is a perfectly
    fine, cheap way to reach a terminal state without any real ffmpeg work.
    """

    def __init__(self, execution_order: list[str]):
        self.execution_order = execution_order
        self.max_concurrent = 0
        self._concurrent = 0
        self._lock = threading.Lock()
        self.release_events: dict[str, threading.Event] = {}
        self.started_events: dict[str, threading.Event] = {}

    def __call__(self, composition_request, scenes_dir, is_cancelled, on_progress, register_process):
        label = composition_request["label"]
        with self._lock:
            self._concurrent += 1
            self.max_concurrent = max(self.max_concurrent, self._concurrent)
        self.execution_order.append(label)
        self.started_events.setdefault(label, threading.Event()).set()
        try:
            if composition_request.get("slow"):
                release = self.release_events.setdefault(label, threading.Event())
                deadline = time.monotonic() + _WAIT_TIMEOUT_SEC
                while time.monotonic() < deadline:
                    if is_cancelled():
                        raise RenderCancelled()
                    if release.is_set():
                        break
                    time.sleep(0.01)
            else:
                time.sleep(0.02)
            return []
        finally:
            with self._lock:
                self._concurrent -= 1


# -- state machine (no worker running -- pure DB/service-method assertions) --


class StateMachineTests(_JobLifecycleTestCase):
    def setUp(self):
        super().setUp()
        self.service = VideoComposerService(library_dir=self.tmp_path)

    def test_queued_job_cancel_transitions_directly_to_cancelled(self):
        job_id = self._make_job("a")
        self.assertEqual(self._get_job(job_id).status, "queued")

        self.assertTrue(self.service.cancel_job(job_id))
        self.assertEqual(self._get_job(job_id).status, "cancelled")
        self.assertIsNotNone(self._get_job(job_id).completed_at)

    def test_running_job_cancel_sets_flag_but_worker_owns_the_actual_transition(self):
        # Simulates a job the (not-yet-started) worker has already moved to
        # a RUNNING-equivalent status -- cancel_job signals it but the DB
        # status only changes once the worker itself observes the flag (see
        # _run_job's checkpoints) -- cancel_job is not a shortcut around
        # that, matching "only the process this job owns is ever touched."
        job_id = self._make_job("a")
        self.service._set_status(job_id, "merging")

        self.assertTrue(self.service.cancel_job(job_id))
        self.assertEqual(self._get_job(job_id).status, "merging")  # unchanged -- worker hasn't observed it yet
        self.assertTrue(self.service._is_cancelled(job_id))

    def test_completed_job_cannot_be_cancelled(self):
        job_id = self._make_job("a")
        self.service._set_status(job_id, "completed")
        self.assertFalse(self.service.cancel_job(job_id))

    def test_failed_job_cannot_be_cancelled(self):
        job_id = self._make_job("a")
        self.service._set_status(job_id, "failed")
        self.assertFalse(self.service.cancel_job(job_id))

    def test_already_cancelled_job_cannot_be_cancelled_again(self):
        job_id = self._make_job("a")
        self.service._set_status(job_id, "cancelled")
        self.assertFalse(self.service.cancel_job(job_id))

    def test_cancelling_a_nonexistent_job_returns_false(self):
        self.assertFalse(self.service.cancel_job(999999))

    def test_coarse_status_covers_every_fine_grained_status(self):
        from app.modules.video_composer.models import VIDEO_COMPOSE_STATUSES

        for status in VIDEO_COMPOSE_STATUSES:
            self.assertIn(status, COARSE_STATUS)
            self.assertIn(COARSE_STATUS[status], {"QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"})


# -- local FIFO queue, single concurrency ------------------------------------


class QueueTests(_JobLifecycleTestCase):
    def setUp(self):
        super().setUp()
        self.fake_renderer = FakeBeatRenderer(self.execution_order)
        self.service = VideoComposerService(library_dir=self.tmp_path, beat_renderer=self.fake_renderer)
        self.service.start()

    def tearDown(self):
        self.service.shutdown()
        super().tearDown()

    def test_fifo_ordering_and_single_concurrency(self):
        job_ids = [self._make_job(label) for label in ("a", "b", "c")]
        for job_id in job_ids:
            self.service.enqueue(job_id)

        for job_id in job_ids:
            self._wait_terminal(job_id)

        self.assertEqual(self.execution_order, ["a", "b", "c"])
        self.assertEqual(self.fake_renderer.max_concurrent, 1)
        # No real clips were ever produced -- each job fails cleanly with a
        # real, specific reason, not silently.
        for job_id in job_ids:
            self.assertEqual(self._get_job(job_id).status, "failed")

    def test_next_job_starts_after_a_running_job_is_cancelled(self):
        slow_job_id = self._make_job("slow", slow=True)
        self.service.enqueue(slow_job_id)
        self._wait_until(lambda: "slow" in self.fake_renderer.started_events and self.fake_renderer.started_events["slow"].is_set())
        self._wait_until(lambda: self._get_job(slow_job_id).status == "rendering_beats")

        fast_job_id = self._make_job("fast")
        self.service.enqueue(fast_job_id)
        # "fast" must NOT start yet -- only one render at a time.
        time.sleep(0.1)
        self.assertNotIn("fast", self.execution_order)

        self.assertTrue(self.service.cancel_job(slow_job_id))
        self.assertEqual(self._wait_terminal(slow_job_id), "cancelled")
        self.assertEqual(self._wait_terminal(fast_job_id), "failed")  # empty clips, same as above
        self.assertEqual(self.execution_order, ["slow", "fast"])
        self.assertEqual(self.fake_renderer.max_concurrent, 1)

    def test_cancelled_running_job_leaves_no_scratch_files(self):
        slow_job_id = self._make_job("slow", slow=True)
        self.service.enqueue(slow_job_id)
        self._wait_until(lambda: self._get_job(slow_job_id).status == "rendering_beats")

        scenes_dir = self.service.job_dir(slow_job_id) / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        (scenes_dir / "fake_partial_clip.mp4").write_bytes(b"partial")

        self.service.cancel_job(slow_job_id)
        self._wait_terminal(slow_job_id)
        self.assertFalse(scenes_dir.exists())

    def test_next_job_starts_after_a_job_fails(self):
        # test_fifo_ordering_and_single_concurrency already proves this (b
        # only runs after a's failure, c only after b's) -- this test names
        # it explicitly for the "next job starts after failure" acceptance
        # criterion on its own.
        job_a = self._make_job("a")
        job_b = self._make_job("b")
        self.service.enqueue(job_a)
        self.service.enqueue(job_b)
        self.assertEqual(self._wait_terminal(job_a), "failed")
        self.assertEqual(self._wait_terminal(job_b), "failed")
        self.assertEqual(self.execution_order, ["a", "b"])


# -- crash recovery -----------------------------------------------------------


class RecoveryTests(_JobLifecycleTestCase):
    def setUp(self):
        super().setUp()
        self.service = VideoComposerService(library_dir=self.tmp_path)

    def test_running_job_is_recovered_as_failed_with_render_interrupted(self):
        job_id = self._make_job("a")
        self.service._set_status(job_id, "mixing_audio")  # simulates a crash mid-render

        self.service._recover_pending_jobs()

        job = self._get_job(job_id)
        self.assertEqual(job.status, "failed")
        self.assertIn("interrupted", job.error_message.lower())

        report_path = self.tmp_path / ".render" / f"job_{job_id}" / "report.json"
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["error_code"], render_errors.RENDER_INTERRUPTED)

    def test_queued_job_is_simply_requeued_on_recovery(self):
        job_id = self._make_job("a")
        self.assertEqual(self._get_job(job_id).status, "queued")

        self.service._recover_pending_jobs()

        self.assertEqual(self._get_job(job_id).status, "queued")  # unchanged, not marked failed
        self.assertEqual(self.service._queue.qsize(), 1)
        self.assertEqual(self.service._queue.get_nowait(), job_id)

    def test_completed_job_is_untouched_by_recovery(self):
        job_id = self._make_job("a")
        self.service._set_status(job_id, "completed")
        self.service._recover_pending_jobs()
        self.assertEqual(self._get_job(job_id).status, "completed")

    def test_retry_after_recovery_creates_a_fresh_job(self):
        job_id = self._make_job("a")
        self.service._set_status(job_id, "finalizing")
        self.service._recover_pending_jobs()
        self.assertEqual(self._get_job(job_id).status, "failed")

        new_job_id = self.service.retry_job(job_id)
        self.assertNotEqual(new_job_id, job_id)
        new_job = self._get_job(new_job_id)
        self.assertEqual(new_job.status, "queued")
        self.assertEqual(new_job.previous_job_id, job_id)
        self.assertEqual(new_job.composition_request_json, self._get_job(job_id).composition_request_json)
        # The original job's own record is untouched by the retry.
        self.assertEqual(self._get_job(job_id).status, "failed")


# -- retry --------------------------------------------------------------------


class RetryTests(_JobLifecycleTestCase):
    def setUp(self):
        super().setUp()
        self.service = VideoComposerService(library_dir=self.tmp_path)

    def test_retry_requires_a_stored_composition_request(self):
        job_id = self.service.create_job(
            title="upload-flow job", script_text="hi", voice="en-US-GuyNeural", music_volume=0.15,
            transition_duration=0.3, burn_subtitles=True, requested_output_dir=None,
        )
        self.service._set_status(job_id, "failed")
        with self.assertRaises(ValidationError):
            self.service.retry_job(job_id)

    def test_retry_rejects_a_completed_job(self):
        job_id = self._make_job("a")
        self.service._set_status(job_id, "completed")
        with self.assertRaises(ValidationError):
            self.service.retry_job(job_id)

    def test_retry_accepts_a_cancelled_job(self):
        job_id = self._make_job("a")
        self.service._set_status(job_id, "cancelled")
        new_job_id = self.service.retry_job(job_id)
        self.assertEqual(self._get_job(new_job_id).status, "queued")


# -- real ffmpeg process termination (not just the checkpoint flag) ---------


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class RealFfmpegCancellationTests(_JobLifecycleTestCase):
    """Task 11 acceptance criterion 11 ("FFmpeg processes are owned and
    safely terminated") specifically, using the real render_beats_for_job
    -> app.modules.motion.renderer.render_motion_clip path and a real
    ffmpeg zoompan render slow enough to still be running when cancel_job
    is called -- not the FakeBeatRenderer's simulated cancellation loop
    above, which only proves the service-level bookkeeping, not that an
    actual OS process gets killed.
    """

    def setUp(self):
        super().setUp()
        self.tmp_path_extra = Path(self.tmpdir.name)
        # A large image + a several-second zoompan duration at a real fps
        # makes ffmpeg do enough per-frame work to still be mid-render a
        # couple hundred ms in -- long enough to reliably observe RUNNING
        # and cancel it, short enough not to slow the suite down much.
        self.image_path = self.tmp_path_extra / "big.jpg"
        Image.new("RGB", (2400, 3200), color=(120, 40, 200)).save(self.image_path, quality=90)

        self.service = VideoComposerService(library_dir=self.tmp_path, beat_renderer=render_beats_for_job)
        self.service.start()

    def tearDown(self):
        self.service.shutdown()
        super().tearDown()

    def test_cancel_terminates_the_actual_ffmpeg_process_promptly(self):
        composition_request = {
            "plan": {
                "scenes": [
                    {
                        "id": "beat_01",
                        "order": 1,
                        "duration": 6.0,
                        "source_asset_id": 101,
                        "motion": {
                            "preset_name": "slow_push_in",
                            "scale": {"start": 1.0, "end": 1.6},
                            "position": {"x_start": 0.5, "y_start": 0.5, "x_end": 0.5, "y_end": 0.5},
                        },
                        "output_format": {"width": 1080, "height": 1920, "fps": 30},
                    }
                ]
            },
            "asset_paths": {"101": str(self.image_path)},
        }
        job_id = self.service.create_job(
            title="cancel test", script_text="", voice="en-US-GuyNeural", music_volume=0.15,
            transition_duration=0.3, burn_subtitles=False, requested_output_dir=None,
            composition_request_json=composition_request,
        )
        self.service.enqueue(job_id)
        self._wait_until(lambda: self._get_job(job_id).status == "rendering_beats")
        # Give ffmpeg a brief moment to actually spawn and start encoding
        # frames (not just have the Python side reach "rendering_beats").
        time.sleep(0.3)

        cancel_start = time.monotonic()
        self.assertTrue(self.service.cancel_job(job_id))
        final_status = self._wait_terminal(job_id, timeout=5.0)
        cancel_elapsed = time.monotonic() - cancel_start

        self.assertEqual(final_status, "cancelled")
        # A full, uncancelled 6s/30fps zoompan render of a 2400x3200 image
        # takes several seconds on typical desktop hardware -- terminating
        # in well under that proves the live ffmpeg process was actually
        # killed, not merely waited out to its natural completion.
        self.assertLess(cancel_elapsed, 3.0)
        self.assertFalse((self.service.job_dir(job_id) / "scenes").exists())


if __name__ == "__main__":
    unittest.main()
