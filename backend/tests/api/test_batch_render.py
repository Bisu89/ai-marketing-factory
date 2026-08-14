"""Integration tests for Task 13's batch orchestration
(app/api/v1/endpoints/batch_render.py) -- see
docs/features/40-batch-video-creation.md. Route handlers are called
directly as plain functions (this codebase's established convention, see
e.g. tests/api/test_composition_render.py), against a single shared,
real (temp file, not :memory:) SQLite database so app.modules.beat.Project,
app.modules.batch.Batch/BatchItem, and app.modules.video_composer.VideoComposeJob
all really interact, exactly as they do in production (one SQLite file).
Each of the four modules involved binds its own `SessionLocal` name at
import time (see each service module's own docstring for why -- supports
a background worker thread using it independently of any one request's
session) -- all four are patched to the same file-backed sessionmaker
below so they genuinely share data, not simulate it.
"""

import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints import batch_render
from app.api.v1.endpoints.composition_render import render_beats_for_job
from app.api.v1.endpoints.batch_render import (
    cancel_batch,
    create_batch,
    generate_beats_for_batch,
    get_batch_detail,
    preview_batch,
    render_batch,
    retry_batch,
    sync_batch,
)
from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService
from app.modules.batch.models import Batch, BatchItem
from app.modules.batch.schemas import CreateBatchRequest
from app.modules.batch.service import set_item_fields
from app.modules.beat.models import Project
from app.modules.beat.project_service import update_project_beat_plan
from app.modules.beat.schemas import Beat, BeatPlan, BeatType
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob
from app.modules.video_composer.service import VideoComposerService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_solid_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (320, 320)) -> Path:
    Image.new("RGB", size, color=color).save(path)
    return path


def _fake_run_narration(script_text: str, voice: str, output_path: Path) -> list[dict]:
    """Stands in for VideoComposerService._run_narration (normally a real
    edge-tts cloud call) with a short local silent track, exactly like
    tests/api/test_composition_render.py's own fixture of the same name --
    keeps these batch-rendering tests free of any network dependency while
    still exercising the real, unmodified render pipeline end to end.
    """
    subprocess.run(
        [
            "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "1.0",
            "-c:a", "libmp3lame", str(output_path),
        ],
        check=True, stdin=subprocess.DEVNULL,
    )
    return [{"start": 0.0, "end": 0.5, "text": "Test"}, {"start": 0.5, "end": 1.0, "text": "narration"}]


def _fake_beat_plan(script_text: str, num_beats: int = 2) -> BeatPlan:
    return BeatPlan(
        script_text=script_text,
        beats=[
            Beat(id=f"beat_{i:02d}", order=i, type=BeatType.BODY, narration=f"{script_text} part {i}", duration=1.5)
            for i in range(1, num_beats + 1)
        ],
    )


class _BatchTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

        # A real temp *file* DB, not :memory:+StaticPool -- the batch beat-
        # generation processor runs several real concurrent threads (see
        # BeatGenerationTests), and StaticPool shares exactly one sqlite3
        # connection object across every thread, which raises "cannot start
        # a transaction within a transaction" the moment two threads try to
        # commit overlapping transactions on it. A file DB (matching how
        # app.db.session.build_engine's *real* engine is configured: no
        # StaticPool there either) gives each SessionLocal() call its own
        # connection, exactly like production.
        self.db_path = self.tmp_path / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                Batch.__table__, BatchItem.__table__, Project.__table__,
                VideoComposeJob.__table__, VideoComposeClip.__table__, Asset.__table__,
            ],
        )
        self.TestSessionLocal = sessionmaker(bind=self.engine)

        self.patchers = [
            patch("app.modules.batch.service.SessionLocal", self.TestSessionLocal),
            patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.batch_render.SessionLocal", self.TestSessionLocal),
            patch("app.modules.video_composer.service.SessionLocal", self.TestSessionLocal),
        ]
        for p in self.patchers:
            p.start()

        self.settings = Settings(library_dir=str(self.tmp_path), anthropic_api_key="fake-test-key")
        # beat_renderer wired exactly like tests/api/test_composition_render.py's
        # own _VideoComposerIntegrationTestCase -- without it, the worker's
        # RENDER_BEATS phase fails immediately with "no beat renderer
        # configured" for every job built via render_composition/render_batch.
        self.service = VideoComposerService(library_dir=self.tmp_path, beat_renderer=render_beats_for_job)

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _db(self):
        return self.TestSessionLocal()

    def _create_batch(self, name: str, template_id: str, scripts_text: str) -> Batch:
        return create_batch(CreateBatchRequest(name=name, template_id=template_id, scripts_text=scripts_text), self.settings)

    def _get_project(self, project_id: int) -> Project:
        db = self._db()
        try:
            return db.get(Project, project_id)
        finally:
            db.close()

    def _get_batch_detail(self, batch_id: int):
        # get_batch_detail's `db` param is normally FastAPI's Depends(get_db)
        # (a generator that closes it after the request) -- calling it
        # directly needs the same explicit close, or the Session's still-
        # checked-out connection isn't returned to self.engine's pool, and
        # self.engine.dispose() in tearDown can't force it closed either
        # (it only closes idle, checked-in connections). On Windows that
        # leftover open connection is exactly what makes the temp-dir
        # cleanup fail with a file-in-use error once a real worker thread
        # has also touched the same file-backed sqlite DB.
        db = self._db()
        try:
            return get_batch_detail(batch_id, db)
        finally:
            db.close()

    def _register_image_asset(self, path: Path) -> int:
        db = self._db()
        try:
            asset = AssetService(db).register(
                AssetRegisterIn(filename=path.name, path=str(path), type="image", source="test")
            )
            return asset.id
        finally:
            db.close()

    def _register_narration_asset(self, duration: float = 1.0) -> int:
        """A short, real, local narration track -- used to keep a render's
        narration_mode "local" instead of "tts" (see _resolve_narration in
        composition_render.py). "tts" mode really does place one external
        edge-tts network call per render (report.json's own
        external_api_calls counts it, correctly), which would make a test
        asserting "batch rendering makes zero external calls" both wrong
        and flaky (a real network dependency) -- "local" mode is what a
        genuinely $0/offline render actually requires, exactly like
        docs/features/36-audio-pipeline.md's own local-narration path.
        """
        narration_path = self.tmp_path / f"narration_{duration}.mp3"
        if not narration_path.exists():
            subprocess.run(
                [
                    "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
                    "-c:a", "libmp3lame", str(narration_path),
                ],
                check=True, stdin=subprocess.DEVNULL,
            )
        db = self._db()
        try:
            asset = AssetService(db).register(
                AssetRegisterIn(filename=narration_path.name, path=str(narration_path), type="audio", source="test")
            )
            return asset.id
        finally:
            db.close()

    def _make_project_render_ready(
        self, item: BatchItem, asset_id: int, num_beats: int = 1, duration: float = 1.0, narration_asset_id: int | None = None
    ) -> None:
        """Simulates the parts of the real workflow batch rendering itself
        doesn't automate yet (visual asset assignment is Task 14's own
        scope, not this one's) -- takes a project that already has a
        beat-less or beat-having draft and gives it a real, renderable
        BeatPlan (real asset_id, PREVIEW profile for fast test renders),
        then marks its BatchItem BEATS_READY, exactly the state a real
        project reaches once a human has generated beats and assigned
        visuals in the UI.
        """
        project = self._get_project(item.project_id)
        plan = BeatPlan(
            script_text=project.beat_plan_json["script_text"],
            beats=[
                Beat(
                    id=f"beat_{i:02d}", order=i, type=BeatType.BODY, narration=f"Part {i}.", duration=duration,
                    asset_id=asset_id, narration_asset_id=narration_asset_id,
                )
                for i in range(1, num_beats + 1)
            ],
            project_name=project.beat_plan_json.get("project_name"),
        )
        plan.config.render.profile = "PREVIEW"
        update_project_beat_plan(item.project_id, plan)
        set_item_fields(item.id, status="BEATS_READY", error_message=None)


# -- Preview + creation -------------------------------------------------


class BatchCreationTests(_BatchTestCase):
    def test_preview_does_not_write_anything(self):
        result = preview_batch(
            CreateBatchRequest(name="Emotional Stories", template_id="emotional_story", scripts_text="A.\n---\nB.\n---\nC."),
            self.settings,
        )
        self.assertEqual(result.script_count, 3)
        self.assertEqual([i.project_name for i in result.items], ["Emotional Stories 001", "Emotional Stories 002", "Emotional Stories 003"])

        db = self._db()
        try:
            self.assertEqual(db.query(Batch).count(), 0)
            self.assertEqual(db.query(Project).count(), 0)
        finally:
            db.close()

    def test_one_script_creates_one_project(self):
        out = self._create_batch("Solo", "custom", "Just one script.")
        self.assertEqual(len(out.items), 1)
        self.assertIsNotNone(out.items[0].project_id)
        project = self._get_project(out.items[0].project_id)
        self.assertEqual(project.name, "Solo 001")
        self.assertEqual(project.beat_plan_json["script_text"], "Just one script.")
        self.assertEqual(project.beat_plan_json["beats"], [])  # no beats yet -- generation hasn't run

    def test_ten_scripts_create_ten_projects(self):
        scripts = "\n---\n".join(f"Script number {i}." for i in range(1, 11))
        out = self._create_batch("Ten Pack", "custom", scripts)
        self.assertEqual(len(out.items), 10)
        self.assertEqual([i.index for i in out.items], list(range(1, 11)))
        project_ids = {i.project_id for i in out.items}
        self.assertEqual(len(project_ids), 10)  # all distinct

    def test_correct_template_applied_to_every_project(self):
        out = self._create_batch("Emotional Batch", "emotional_story", "A.\n---\nB.")
        for item in out.items:
            project = self._get_project(item.project_id)
            config = project.beat_plan_json["config"]
            self.assertEqual(config["motion"]["default_preset"], "SLOW_PUSH_IN")
            self.assertEqual(config["captions"]["preset"], "big_statement")
            self.assertEqual(config["template_id"], "emotional_story")

    def test_project_configuration_is_isolated_per_project(self):
        out = self._create_batch("Isolation Check", "emotional_story", "A.\n---\nB.")
        project_a = self._get_project(out.items[0].project_id)
        project_b = self._get_project(out.items[1].project_id)

        db = self._db()
        try:
            row_a = db.get(Project, project_a.id)
            row_a.beat_plan_json = {**row_a.beat_plan_json, "config": {**row_a.beat_plan_json["config"]}}
            row_a.beat_plan_json["config"]["motion"]["default_preset"] = "PAN_RIGHT"
            db.commit()
        finally:
            db.close()

        project_b_after = self._get_project(project_b.id)
        self.assertEqual(project_b_after.beat_plan_json["config"]["motion"]["default_preset"], "SLOW_PUSH_IN")

    def test_duplicate_scripts_create_two_distinct_items(self):
        out = self._create_batch("Dupes", "custom", "Same text.\n---\nSame text.")
        self.assertEqual(len(out.items), 2)
        self.assertNotEqual(out.items[0].project_id, out.items[1].project_id)
        self.assertEqual(out.items[0].script_text, out.items[1].script_text)

    def test_empty_scripts_text_is_rejected_before_any_write(self):
        with self.assertRaises(ValidationError):
            self._create_batch("Empty", "custom", "   \n---\n   ")
        db = self._db()
        try:
            self.assertEqual(db.query(Batch).count(), 0)
        finally:
            db.close()

    def test_unknown_template_is_rejected_before_any_write(self):
        with self.assertRaises(NotFoundError):
            self._create_batch("Bad Template", "not_a_real_template", "A script.")
        db = self._db()
        try:
            self.assertEqual(db.query(Batch).count(), 0)
            self.assertEqual(db.query(Project).count(), 0)
        finally:
            db.close()

    def test_creation_failure_partway_rolls_back_the_whole_batch(self):
        # Simulate a real failure after some projects already got flushed
        # within the same transaction -- the whole thing must still roll
        # back to zero rows (Task 13 section 14), not leave the first two
        # projects committed.
        real_unique_slug = batch_render.unique_project_slug
        call_count = {"n": 0}

        def _flaky_slug(base, db):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise RuntimeError("simulated failure mid-batch-creation")
            return real_unique_slug(base, db)

        with patch("app.api.v1.endpoints.batch_render.unique_project_slug", side_effect=_flaky_slug):
            with self.assertRaises(RuntimeError):
                self._create_batch("Will Fail", "custom", "One.\n---\nTwo.\n---\nThree.\n---\nFour.")

        db = self._db()
        try:
            self.assertEqual(db.query(Batch).count(), 0)
            self.assertEqual(db.query(Project).count(), 0)
        finally:
            db.close()


# -- Beat generation ------------------------------------------------------


class BeatGenerationTests(_BatchTestCase):
    def test_successful_generation_marks_items_beats_ready(self):
        out = self._create_batch("Gen Test", "custom", "Script A.\n---\nScript B.")
        with patch("app.api.v1.endpoints.batch_render.generate_beat_plan", side_effect=lambda key, script: _fake_beat_plan(script)):
            generate_beats_for_batch(out.id, self.settings)
            # Background thread -- wait for it to actually finish.
            self._wait_for_terminal_batch_status(out.id, timeout=5.0)

        detail = self._get_batch_detail(out.id)
        self.assertTrue(all(item.status == "BEATS_READY" for item in detail.items))
        project = self._get_project(detail.items[0].project_id)
        self.assertEqual(len(project.beat_plan_json["beats"]), 2)

    def test_generation_failure_marks_only_that_item_failed(self):
        out = self._create_batch("Partial Gen Fail", "custom", "Good.\n---\nBad.")

        def _maybe_fail(key, script):
            if script == "Bad.":
                raise ValueError("Model returned zero beats")
            return _fake_beat_plan(script)

        with patch("app.api.v1.endpoints.batch_render.generate_beat_plan", side_effect=_maybe_fail):
            generate_beats_for_batch(out.id, self.settings)
            self._wait_for_terminal_batch_status(out.id, timeout=5.0)

        detail = self._get_batch_detail(out.id)
        statuses = {item.script_text: item.status for item in detail.items}
        self.assertEqual(statuses["Good."], "BEATS_READY")
        self.assertEqual(statuses["Bad."], "FAILED")
        self.assertEqual(detail.status, "PARTIAL_FAILURE")

    def test_concurrency_is_bounded(self):
        out = self._create_batch("Concurrency", "custom", "\n---\n".join(f"S{i}" for i in range(6)))
        max_seen = {"n": 0}
        current = {"n": 0}
        lock = threading.Lock()

        def _slow_generate(key, script):
            with lock:
                current["n"] += 1
                max_seen["n"] = max(max_seen["n"], current["n"])
            time.sleep(0.1)
            with lock:
                current["n"] -= 1
            return _fake_beat_plan(script)

        self.settings.max_concurrent_ai_generation = 2
        with patch("app.api.v1.endpoints.batch_render.generate_beat_plan", side_effect=_slow_generate):
            generate_beats_for_batch(out.id, self.settings)
            self._wait_for_terminal_batch_status(out.id, timeout=10.0)

        self.assertLessEqual(max_seen["n"], 2)

    def _wait_for_terminal_batch_status(self, batch_id: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            db = self._db()
            try:
                batch = db.get(Batch, batch_id)
                if batch.status != "PROCESSING":
                    return
            finally:
                db.close()
            time.sleep(0.02)
        self.fail("batch never left PROCESSING")


# -- Render queue integration (reuses the existing single-worker queue) --


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class RenderQueueIntegrationTests(_BatchTestCase):
    """Proves batch rendering (render_batch) really goes through the
    *existing* VideoComposerService queue/worker (Task 8/11), not a second
    one -- see batch_render.py's own module docstring. Each test that needs
    a job to actually finish calls self.service.start() itself rather than
    in setUp, so tests that don't need the worker running (e.g. the cancel
    test below, which cancels still-queued jobs) stay deterministic with no
    timing race. tearDown shuts the worker down *before* the base class's
    tempdir cleanup runs (unlike addCleanup, which would run after -- on
    Windows a still-open sqlite connection from a live worker thread makes
    the temp-dir teardown fail with a file-in-use error).
    """

    def setUp(self):
        super().setUp()
        self.image = _make_solid_image(self.tmp_path / "shared_beat.jpg", (200, 40, 40))
        self.asset_id = self._register_image_asset(self.image)

    def tearDown(self):
        self.service.shutdown()
        super().tearDown()

    def _get_job_row(self, job_id: int) -> VideoComposeJob:
        db = self._db()
        try:
            return db.get(VideoComposeJob, job_id)
        finally:
            db.close()

    def _wait_for_jobs_terminal(self, job_ids: list[int], timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            jobs = [self._get_job_row(jid) for jid in job_ids]
            if all(j.status in ("completed", "failed", "cancelled") for j in jobs):
                return
            time.sleep(0.2)
        self.fail("render jobs never reached a terminal status")

    def test_multiple_ready_items_all_render_and_complete(self):
        narration_asset_id = self._register_narration_asset(duration=0.8)
        out = self._create_batch("Queue Test", "custom", "One.\n---\nTwo.\n---\nThree.")
        for item in out.items:
            self._make_project_render_ready(item, self.asset_id, duration=1.0, narration_asset_id=narration_asset_id)

        self.service.start()

        db = self._db()
        try:
            result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()

        self.assertTrue(all(i.status == "RENDERING" for i in result.items))
        job_ids = [i.render_job_id for i in result.items]
        self.assertEqual(len(set(job_ids)), 3)  # each item got its own real RenderJob

        self._wait_for_jobs_terminal(job_ids, timeout=60.0)

        detail = self._get_batch_detail(out.id)
        self.assertTrue(all(i.status == "COMPLETED" for i in detail.items), [(i.status, i.error_message) for i in detail.items])
        self.assertEqual(detail.status, "COMPLETED")

        for job_id in job_ids:
            job = self._get_job_row(job_id)
            self.assertTrue(Path(job.output_path).exists())
            report_path = self.tmp_path / ".render" / f"job_{job_id}" / "report.json"
            self.assertTrue(report_path.exists())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["external_api_calls"], 0)
            self.assertEqual(report["external_api_cost_estimate"], 0)

    def test_only_one_render_job_runs_at_a_time(self):
        out = self._create_batch("Serial Test", "custom", "One.\n---\nTwo.\n---\nThree.")
        for item in out.items:
            self._make_project_render_ready(item, self.asset_id, duration=1.0)

        current = {"n": 0}
        max_seen = {"n": 0}
        lock = threading.Lock()
        real_run_job = self.service._run_job

        def _tracked_run_job(job_id):
            with lock:
                current["n"] += 1
                max_seen["n"] = max(max_seen["n"], current["n"])
            try:
                real_run_job(job_id)
            finally:
                with lock:
                    current["n"] -= 1

        self.service.start()

        with patch.object(self.service, "_run_job", side_effect=_tracked_run_job), \
             patch.object(self.service, "_run_narration", side_effect=_fake_run_narration):
            db = self._db()
            try:
                result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
            finally:
                db.close()
            job_ids = [i.render_job_id for i in result.items]
            self._wait_for_jobs_terminal(job_ids, timeout=60.0)

        self.assertEqual(max_seen["n"], 1)  # never more than one render in flight

    def test_failed_render_does_not_block_completion_of_other_items(self):
        corrupt = self.tmp_path / "corrupt.jpg"
        corrupt.write_bytes(b"not a real image")
        corrupt_asset_id = self._register_image_asset(corrupt)

        out = self._create_batch("Partial Render Failure", "custom", "Good one.\n---\nBad one.\n---\nGood two.")
        items_by_script = {i.script_text: i for i in out.items}
        self._make_project_render_ready(items_by_script["Good one."], self.asset_id, duration=1.0)
        self._make_project_render_ready(items_by_script["Bad one."], corrupt_asset_id, duration=1.0)
        self._make_project_render_ready(items_by_script["Good two."], self.asset_id, duration=1.0)

        self.service.start()

        with patch.object(self.service, "_run_narration", side_effect=_fake_run_narration):
            db = self._db()
            try:
                result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
            finally:
                db.close()
            job_ids = [i.render_job_id for i in result.items]
            self._wait_for_jobs_terminal(job_ids, timeout=60.0)

        detail = self._get_batch_detail(out.id)
        statuses = {i.script_text: i.status for i in detail.items}
        self.assertEqual(statuses["Good one."], "COMPLETED")
        self.assertEqual(statuses["Good two."], "COMPLETED")
        self.assertEqual(statuses["Bad one."], "FAILED")
        self.assertEqual(detail.status, "PARTIAL_FAILURE")

    def test_cancel_batch_cancels_queued_render_jobs(self):
        # Worker deliberately never started (self.service.start() not
        # called) -- every enqueued job stays "queued" forever, so
        # cancel_job's immediate-cancel-of-queued-jobs path (Task 11) runs
        # deterministically, with no race against a real worker thread.
        out = self._create_batch("Cancel Test", "custom", "One.\n---\nTwo.")
        for item in out.items:
            self._make_project_render_ready(item, self.asset_id, duration=1.0)

        db = self._db()
        try:
            result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()
        self.assertTrue(all(i.status == "RENDERING" for i in result.items))

        cancelled = cancel_batch(out.id, service=self.service)
        self.assertTrue(all(i.status == "CANCELLED" for i in cancelled.items))
        self.assertEqual(cancelled.status, "CANCELLED")

        for item in cancelled.items:
            job = self._get_job_row(item.render_job_id)
            self.assertEqual(job.status, "cancelled")


# -- Retry (only FAILED/SKIPPED touched, never a completed render) -------


class RetryTests(_BatchTestCase):
    def _wait_for_terminal_batch_status(self, batch_id: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            db = self._db()
            try:
                batch = db.get(Batch, batch_id)
                if batch.status != "PROCESSING":
                    return
            finally:
                db.close()
            time.sleep(0.02)
        self.fail("batch never left PROCESSING")

    def test_retry_of_failed_item_with_no_beats_retriggers_beat_generation(self):
        out = self._create_batch("Retry Beat Gen", "custom", "Retry me.")
        item = out.items[0]
        set_item_fields(item.id, status="FAILED", error_message="model error")

        with patch("app.api.v1.endpoints.batch_render.generate_beat_plan", side_effect=lambda key, script: _fake_beat_plan(script)):
            db = self._db()
            try:
                retry_batch(out.id, db=db, settings=self.settings, service=self.service)
            finally:
                db.close()
            self._wait_for_terminal_batch_status(out.id, timeout=5.0)

        detail = self._get_batch_detail(out.id)
        self.assertEqual(detail.items[0].status, "BEATS_READY")

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_retry_of_failed_item_with_existing_beats_retriggers_render(self):
        image = _make_solid_image(self.tmp_path / "retry.jpg", (10, 200, 10))
        asset_id = self._register_image_asset(image)

        out = self._create_batch("Retry Render", "custom", "Has beats already.")
        item = out.items[0]
        self._make_project_render_ready(item, asset_id, duration=1.0)
        set_item_fields(item.id, status="FAILED", error_message="render blew up", render_job_id=None)

        db = self._db()
        try:
            result = retry_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()

        self.assertEqual(result.items[0].status, "RENDERING")
        self.assertIsNotNone(result.items[0].render_job_id)

    def test_retry_never_touches_a_completed_item(self):
        out = self._create_batch("Retry Completed", "custom", "Already done.")
        item = out.items[0]
        set_item_fields(item.id, status="COMPLETED", render_job_id=999, error_message=None)

        db = self._db()
        try:
            result = retry_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()

        self.assertEqual(result.items[0].status, "COMPLETED")
        self.assertEqual(result.items[0].render_job_id, 999)


# -- Full end-to-end: 5 scripts -> 5 projects -> 5 real final.mp4 files ---


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class EndToEndBatchTests(_BatchTestCase):
    """Task 13's own literal end-to-end scenario (see the task brief's
    manual-verification section): 5 scripts -> 5 projects -> 5 real,
    locally-rendered final.mp4 files through the *existing* render queue,
    with zero external video-rendering API calls/cost. Runs the real
    VideoComposerService worker thread (service.start()) rather than
    calling _run_job directly, so this also proves batch rendering truly
    goes through the one existing queue end to end, not a shortcut.

    Visual-asset assignment (mapping each Beat to a real local image) is
    done directly against each Project's beat_plan_json here, not through
    any batch-level automation -- that automation is Task 14's own scope
    ("Asset Automation: Beat -> Visual Asset Assignment"), not this one's;
    this mirrors the one manual step a human currently does in the Video
    Factory UI between "Generate Beats" and "Render All."
    """

    def setUp(self):
        super().setUp()
        self.asset_ids = [
            self._register_image_asset(_make_solid_image(self.tmp_path / f"beat_{i}.jpg", color))
            for i, color in enumerate([(200, 40, 40), (40, 200, 40), (40, 40, 200), (200, 200, 40), (200, 40, 200)])
        ]

    def tearDown(self):
        # Shut the worker down *before* the base class's tempdir cleanup --
        # see RenderQueueIntegrationTests.tearDown's own comment for why
        # addCleanup (which would run after tearDown) is the wrong tool here.
        self.service.shutdown()
        super().tearDown()

    def _wait_for_terminal_batch_status(self, batch_id: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            db = self._db()
            try:
                batch = db.get(Batch, batch_id)
                if batch.status != "PROCESSING":
                    return
            finally:
                db.close()
            time.sleep(0.02)
        self.fail("batch never left PROCESSING")

    def test_five_scripts_render_to_five_real_final_mp4_files_at_zero_video_cost(self):
        scripts = "\n---\n".join(f"Script number {i}: a short story." for i in range(1, 6))
        out = self._create_batch("E2E Five Pack", "custom", scripts)
        self.assertEqual(len(out.items), 5)

        with patch("app.api.v1.endpoints.batch_render.generate_beat_plan", side_effect=lambda key, script: _fake_beat_plan(script, num_beats=2)):
            generate_beats_for_batch(out.id, self.settings)
            self._wait_for_terminal_batch_status(out.id, timeout=10.0)

        detail = self._get_batch_detail(out.id)
        self.assertTrue(all(i.status == "BEATS_READY" for i in detail.items))

        # Visual + local narration assignment (the one manual step this
        # batch pipeline doesn't automate yet -- see class docstring). Local
        # narration (not "tts") is what keeps this a genuinely zero-
        # external-API-call render, exactly like _register_narration_asset's
        # own docstring explains.
        narration_asset_id = self._register_narration_asset(duration=1.0)
        for index, item in enumerate(detail.items):
            project = self._get_project(item.project_id)
            plan = BeatPlan.model_validate(project.beat_plan_json)
            for beat in plan.beats:
                beat.asset_id = self.asset_ids[index]
                beat.narration_asset_id = narration_asset_id
            plan.config.render.profile = "PREVIEW"
            update_project_beat_plan(item.project_id, plan)

        self.service.start()

        db = self._db()
        try:
            result = render_batch(out.id, db=db, settings=self.settings, service=self.service)
        finally:
            db.close()

        self.assertTrue(all(i.status == "RENDERING" for i in result.items))
        job_ids = [i.render_job_id for i in result.items]
        self.assertEqual(len(set(job_ids)), 5)

        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            db = self._db()
            try:
                jobs = [db.get(VideoComposeJob, jid) for jid in job_ids]
            finally:
                db.close()
            if all(j.status in ("completed", "failed", "cancelled") for j in jobs):
                break
            time.sleep(0.3)
        else:
            self.fail("not all 5 render jobs reached a terminal status in time")

        final_detail = self._get_batch_detail(out.id)
        self.assertTrue(
            all(i.status == "COMPLETED" for i in final_detail.items),
            [(i.status, i.error_message) for i in final_detail.items],
        )
        self.assertEqual(final_detail.status, "COMPLETED")

        total_external_calls = 0
        total_external_cost = 0.0
        for job_id in job_ids:
            db = self._db()
            try:
                job = db.get(VideoComposeJob, job_id)
            finally:
                db.close()
            output_path = Path(job.output_path)
            self.assertTrue(output_path.exists())

            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(output_path)],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
            )
            self.assertIn("video", set(probe.stdout.split()))

            report_path = self.tmp_path / ".render" / f"job_{job_id}" / "report.json"
            self.assertTrue(report_path.exists())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["external_api_calls"], 0)
            self.assertEqual(report["external_api_cost_estimate"], 0)
            total_external_calls += report["external_api_calls"]
            total_external_cost += report["external_api_cost_estimate"]

        # 5 real local renders, zero external video-generation API calls or
        # cost -- Task 13's own headline cost claim, verified, not asserted.
        self.assertEqual(total_external_calls, 0)
        self.assertEqual(total_external_cost, 0)


if __name__ == "__main__":
    unittest.main()
