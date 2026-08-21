"""Tests for Task 26 -- see docs/features/52-final-composer.md. Reuses
tests.api.test_factory_pipeline's own _FactoryTestCase harness. Uses the
real LocalTTSProvider, real FFmpeg Motion rendering, real Audio Master
mixing, and real Caption Engine segmentation/ASS output throughout (no
mocking of any pipeline stage) -- the same "exercise the real engine"
precedent every prior stage's own tests already established.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.api.v1.endpoints.audio_generate import generate_project_audio_master
from app.api.v1.endpoints.caption_generate import generate_project_captions
from app.api.v1.endpoints.factory_pipeline import FactoryStageError, _stage_render
from app.api.v1.endpoints.voice_generate import generate_project_narration
from app.core import render_errors
from app.modules.beat.project_service import get_project_draft, update_project_beat_plan
from app.modules.beat.schemas import (
    Beat,
    BeatPlan,
    BeatType,
    CaptionsProjectConfig,
    OutroProjectConfig,
    ProjectConfig,
    WatermarkProjectConfig,
)
from app.modules.video_composer.models import VideoComposeJob
from app.modules.video_composer.service import VideoComposerService
from tests.api.test_batch_render import FFMPEG_AVAILABLE, _make_solid_image
from tests.api.test_factory_pipeline import _FactoryTestCase


def _make_watermark_png(path: Path, size: tuple[int, int] = (200, 80)) -> Path:
    Image.new("RGBA", size, color=(255, 255, 255, 160)).save(path)
    return path


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class _FinalComposerTestCase(_FactoryTestCase):
    def setUp(self):
        super().setUp()
        # _FactoryTestCase's own default harness never starts the worker
        # thread (see its _wait_for_run_settled docstring) -- these tests
        # need a real render to actually complete, not just reach QUEUED.
        self.service.start()

    def _full_pipeline_project(
        self, name: str, texts: list[str], *, watermark: WatermarkProjectConfig | None = None,
        captions: CaptionsProjectConfig | None = None, outro: OutroProjectConfig | None = None,
    ) -> int:
        """Beat -> real Voice -> real Motion (via _stage_render's own
        render_beats_for_job) -> real Audio Master -> real Captions, ready
        for _stage_render. Motion clips are produced lazily by
        render_beats_for_job itself (the same beat_renderer the whole
        Factory already uses) -- nothing here calls app.modules.motion
        directly, matching this task's own "reuse the existing renderer"
        instruction.
        """
        from app.modules.beat.project_service import create_project

        config = ProjectConfig()
        if watermark is not None:
            config = config.model_copy(update={"watermark": watermark})
        if captions is not None:
            config = config.model_copy(update={"captions": captions})
        if outro is not None:
            config = config.model_copy(update={"outro": outro})
        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project(name, "placeholder script", config)

        beats = []
        for i, text in enumerate(texts, start=1):
            image = _make_solid_image(self.tmp_path / f"{name}_beat{i}.jpg", (10 * i, 200, 40))
            asset_id = self._register_image_asset(image)
            beats.append(Beat(id=f"b{i}", order=i, type=BeatType.BODY, narration=text, duration=2.0, asset_id=asset_id))

        draft = get_project_draft(project_id)
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)

        generate_project_narration(project_id, self.settings)
        generate_project_audio_master(project_id, self.settings)
        generate_project_captions(project_id, self.settings)
        return project_id

    def _render_final(self, project_id: int) -> VideoComposeJob:
        """Runs _stage_render synchronously against a real FactoryRun, then
        waits for VideoComposerService's own worker to settle the resulting
        VideoComposeJob -- mirrors _FactoryTestCase._run_sync's own
        "no background thread, no race to wait out" shape but for this
        stage alone (the earlier stages are already real artifacts on disk
        by the time this is called, see _full_pipeline_project above).
        """
        from app.modules.factory import service as factory_service

        run, _created = factory_service.create_run(project_id)
        draft = get_project_draft(project_id)
        plan = BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=draft.config)
        _stage_render(run.id, project_id, plan, self.settings, self.service)
        after = self._get_run(run.id)
        assert after.render_job_id is not None, "no render job was queued"
        return self._wait_for_job(after.render_job_id)

    def _wait_for_job(self, job_id: int, timeout: float = 60.0) -> VideoComposeJob:
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            db = self._db()
            try:
                job = db.get(VideoComposeJob, job_id)
                if job is not None and job.status in ("completed", "failed", "cancelled"):
                    db.expunge(job)
                    return job
            finally:
                db.close()
            time.sleep(0.1)
        self.fail("VideoComposeJob never reached a terminal status")

    def _ffprobe_streams(self, path: Path) -> dict:
        import subprocess

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height",
             "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        return json.loads(result.stdout)


class EndToEndCompositionTests(_FinalComposerTestCase):
    def test_three_beats_produce_a_playable_final_video_with_captions(self):
        project_id = self._full_pipeline_project(
            "Final Composer E2E", ["This is the first beat of narration.", "This is the second beat now.", "And the third and final beat."],
        )
        job = self._render_final(project_id)
        self.assertEqual(job.status, "completed")
        self.assertTrue(job.burn_subtitles)
        self.assertIsNotNone(job.output_path)
        out = Path(job.output_path)
        self.assertTrue(out.exists())

        data = self._ffprobe_streams(out)
        video_streams = [s for s in data["streams"] if s["codec_type"] == "video"]
        audio_streams = [s for s in data["streams"] if s["codec_type"] == "audio"]
        self.assertEqual(len(video_streams), 1)
        self.assertEqual(len(audio_streams), 1)
        self.assertEqual(video_streams[0]["codec_name"], "h264")
        self.assertEqual(audio_streams[0]["codec_name"], "aac")


class CaptionsToggleTests(_FinalComposerTestCase):
    def test_captions_disabled_still_produces_a_valid_final_video(self):
        project_id = self._full_pipeline_project(
            "Captions Off Final", ["Some narration text for this beat."], captions=CaptionsProjectConfig(enabled=False),
        )
        job = self._render_final(project_id)
        self.assertEqual(job.status, "completed")
        self.assertFalse(job.burn_subtitles)
        self.assertIsNone(job.captions_ass_path)


class WatermarkTests(_FinalComposerTestCase):
    def test_watermark_disabled_by_default_no_overlay(self):
        project_id = self._full_pipeline_project("Watermark Off Final", ["Some narration text."])
        job = self._render_final(project_id)
        self.assertEqual(job.status, "completed")
        self.assertFalse(job.watermark_enabled)

    def test_watermark_enabled_with_real_png_composes_successfully(self):
        watermark_image = _make_watermark_png(self.tmp_path / "watermark.png")
        watermark_asset_id = self._register_image_asset(watermark_image)
        project_id = self._full_pipeline_project(
            "Watermark On Final", ["Some narration text."],
            watermark=WatermarkProjectConfig(enabled=True, asset_id=watermark_asset_id, position="bottom-right", opacity=0.5, scale=0.2),
        )
        job = self._render_final(project_id)
        self.assertEqual(job.status, "completed")
        self.assertTrue(job.watermark_enabled)
        self.assertTrue(Path(job.output_path).exists())


class OutroCardTests(_FinalComposerTestCase):
    def test_outro_disabled_by_default_no_extra_duration(self):
        project_id = self._full_pipeline_project("Outro Off Final", ["Some narration text for the outro test."])
        job = self._render_final(project_id)
        self.assertEqual(job.status, "completed")
        self.assertIsNone(job.outro_clip_path)

    def test_outro_enabled_extends_final_video_by_its_own_duration(self):
        project_id = self._full_pipeline_project(
            "Outro On Final", ["Some narration text for the outro test."],
            outro=OutroProjectConfig(enabled=True, text="Theo doi de xem phan 2 nhe!", duration_sec=5.0),
        )
        job_without_outro_duration = self._probe_narration_only_duration(project_id)
        job = self._render_final(project_id)
        self.assertEqual(job.status, "completed")
        self.assertIsNotNone(job.outro_clip_path)
        self.assertTrue(Path(job.outro_clip_path).exists())

        streams = self._ffprobe_streams(Path(job.output_path))
        final_duration = float(streams["format"]["duration"])
        # The main composition's own duration (narration-driven) plus the
        # pre-outro hold (docs/features/94-outro-pre-hold.md,
        # _PRE_OUTRO_HOLD_SEC=1.5) plus the outro's own 5.0s -- real, both
        # real ffmpeg-probed values, not a mocked stand-in (this codebase's
        # own "exercise the real engine" precedent for this whole file).
        self.assertAlmostEqual(final_duration, job_without_outro_duration + 1.5 + 5.0, delta=1.0)

    def test_blank_outro_text_is_treated_as_not_configured(self):
        project_id = self._full_pipeline_project(
            "Outro Blank Text Final", ["Some narration text."],
            outro=OutroProjectConfig(enabled=True, text="   ", duration_sec=5.0),
        )
        job = self._render_final(project_id)
        self.assertEqual(job.status, "completed")
        self.assertIsNone(job.outro_clip_path)

    def _probe_narration_only_duration(self, project_id: int) -> float:
        from app.api.v1.endpoints.audio_generate import audio_master_path

        return self.service._probe_duration(audio_master_path(project_id, self.settings.library_dir))


class MissingAudioMasterTests(_FinalComposerTestCase):
    def test_render_fails_fast_when_audio_master_was_never_generated(self):
        from app.modules.beat.project_service import create_project

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            project_id = create_project("No Audio Master", "placeholder", ProjectConfig())
        image = _make_solid_image(self.tmp_path / "no_audio_beat.jpg", (10, 200, 40))
        asset_id = self._register_image_asset(image)
        draft = get_project_draft(project_id)
        beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Some text.", duration=2.0, asset_id=asset_id)]
        plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(project_id, plan)
        # Voice/Audio deliberately never run -- no audio_master.wav exists.

        from app.modules.factory import service as factory_service

        run, _created = factory_service.create_run(project_id)
        with self.assertRaises(FactoryStageError) as ctx:
            _stage_render(run.id, project_id, plan, self.settings, self.service)
        self.assertEqual(ctx.exception.code, render_errors.AUDIO_MASTER_MISSING)
        self.assertEqual(ctx.exception.stage, "READY_TO_RENDER")


class MissingWatermarkAssetTests(_FinalComposerTestCase):
    def test_render_fails_fast_when_watermark_asset_no_longer_exists(self):
        project_id = self._full_pipeline_project(
            "Missing Watermark Asset", ["Some narration text."],
            watermark=WatermarkProjectConfig(enabled=True, asset_id=999999),
        )
        from app.modules.factory import service as factory_service

        run, _created = factory_service.create_run(project_id)
        draft = get_project_draft(project_id)
        plan = BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=draft.config)
        with self.assertRaises(FactoryStageError) as ctx:
            _stage_render(run.id, project_id, plan, self.settings, self.service)
        self.assertEqual(ctx.exception.code, render_errors.WATERMARK_ARTIFACT_MISSING)


def _make_silent_clip(path: Path, duration: float, color: str = "red", width: int = 320, height: int = 568, fps: float = 24.0) -> Path:
    import subprocess

    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-an", str(path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


def _make_silent_audio(path: Path, duration: float) -> Path:
    import subprocess

    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration}", str(path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


class DirectFinalCompositionTests(_FinalComposerTestCase):
    """Calls VideoComposerService._run_final_composition directly (bypassing
    enqueue/the worker thread) for input-validation failure modes -- a
    focused, race-free way to exercise section 6/8/13's own checks without
    depending on live worker-thread timing.
    """

    def _create_precomposed_job(self, audio_master_path: str) -> tuple[int, Path, Path]:
        import uuid

        work_dir = self.tmp_path / f"direct_composition_{uuid.uuid4().hex}"
        output_dir = work_dir / "output"
        tmp_dir = work_dir / "tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        db = self._db()
        try:
            job = VideoComposeJob(
                title="direct", script_text="", voice="v", music_volume=0.0,
                narration_mode="precomposed", audio_master_path=audio_master_path, status="queued",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
        finally:
            db.close()
        return job_id, output_dir, tmp_dir

    def test_missing_beat_clip_fails_with_missing_beat_artifact(self):
        clip = _make_silent_clip(self.tmp_path / "clip_a.mp4", 2.0)
        missing_clip = self.tmp_path / "does_not_exist.mp4"
        audio = _make_silent_audio(self.tmp_path / "audio_a.wav", 4.0)
        job_id, output_dir, tmp_dir = self._create_precomposed_job(str(audio))

        self.service._run_final_composition(
            job_id, [clip, missing_clip], str(audio), None, None,
            "bottom-right", 1.0, 0.15, 24, 24, output_dir, tmp_dir, None, None,
        )
        job = self._wait_for_job(job_id)
        self.assertEqual(job.status, "failed")
        self.assertFalse((output_dir / "video_hoan_chinh.mp4").exists())
        report = json.loads((self.tmp_path / ".render" / f"job_{job_id}" / "report.json").read_text(encoding="utf-8"))
        self.assertIn(render_errors.MISSING_BEAT_ARTIFACT, report["message"])
        self.assertEqual(report["error_code"], render_errors.FINAL_COMPOSITION_FAILED)

    def test_corrupted_beat_clip_fails_before_producing_valid_output(self):
        clip = _make_silent_clip(self.tmp_path / "clip_b.mp4", 2.0)
        corrupt_clip = self.tmp_path / "corrupt.mp4"
        corrupt_clip.write_bytes(b"not a real video file")
        audio = _make_silent_audio(self.tmp_path / "audio_b.wav", 4.0)
        job_id, output_dir, tmp_dir = self._create_precomposed_job(str(audio))

        self.service._run_final_composition(
            job_id, [clip, corrupt_clip], str(audio), None, None,
            "bottom-right", 1.0, 0.15, 24, 24, output_dir, tmp_dir, None, None,
        )
        job = self._wait_for_job(job_id)
        self.assertEqual(job.status, "failed")
        self.assertFalse((output_dir / "video_hoan_chinh.mp4").exists())
        report = json.loads((self.tmp_path / ".render" / f"job_{job_id}" / "report.json").read_text(encoding="utf-8"))
        self.assertIn(render_errors.INVALID_BEAT_ARTIFACT, report["message"])

    def test_duration_mismatch_beyond_tolerance_fails(self):
        # 2s of video vs 10s of audio -- far beyond _FINAL_DURATION_TOLERANCE_SEC.
        clip = _make_silent_clip(self.tmp_path / "clip_c.mp4", 2.0)
        audio = _make_silent_audio(self.tmp_path / "audio_c.wav", 10.0)
        job_id, output_dir, tmp_dir = self._create_precomposed_job(str(audio))

        self.service._run_final_composition(
            job_id, [clip], str(audio), None, None,
            "bottom-right", 1.0, 0.15, 24, 24, output_dir, tmp_dir, None, None,
        )
        job = self._wait_for_job(job_id)
        self.assertEqual(job.status, "failed")
        report = json.loads((self.tmp_path / ".render" / f"job_{job_id}" / "report.json").read_text(encoding="utf-8"))
        self.assertIn(render_errors.FINAL_DURATION_MISMATCH, report["message"])

    def test_valid_inputs_produce_a_playable_final_video_directly(self):
        clip_a = _make_silent_clip(self.tmp_path / "clip_d1.mp4", 2.0)
        clip_b = _make_silent_clip(self.tmp_path / "clip_d2.mp4", 2.0)
        audio = _make_silent_audio(self.tmp_path / "audio_d.wav", 4.0)
        job_id, output_dir, tmp_dir = self._create_precomposed_job(str(audio))

        self.service._run_final_composition(
            job_id, [clip_a, clip_b], str(audio), None, None,
            "bottom-right", 1.0, 0.15, 24, 24, output_dir, tmp_dir, None, None,
        )
        job = self._wait_for_job(job_id)
        self.assertEqual(job.status, "completed")
        self.assertTrue((output_dir / "video_hoan_chinh.mp4").exists())


class CrashRecoveryTests(_FinalComposerTestCase):
    def test_a_job_stuck_composing_final_recovers_as_failed_on_restart(self):
        project_id = self._full_pipeline_project("Composing Crash", ["Some narration text."])
        from app.modules.factory import service as factory_service

        run, _created = factory_service.create_run(project_id)
        draft = get_project_draft(project_id)
        plan = BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=draft.config)
        _stage_render(run.id, project_id, plan, self.settings, self.service)
        after = self._get_run(run.id)
        self._wait_for_job(after.render_job_id)  # let it actually finish first

        # Now simulate an interrupted *second* job stuck in the new phase.
        db = self._db()
        try:
            stuck = VideoComposeJob(
                title="stuck", script_text="", voice="v", music_volume=0.0, status="composing_final",
                audio_master_path="/does/not/matter.wav",
            )
            db.add(stuck)
            db.commit()
            db.refresh(stuck)
            stuck_id = stuck.id
        finally:
            db.close()

        self.service._recover_pending_jobs()
        db = self._db()
        try:
            recovered = db.get(VideoComposeJob, stuck_id)
            self.assertEqual(recovered.status, "failed")
            self.assertEqual(recovered.error_message, "Render was interrupted by an application restart.")
        finally:
            db.close()


class BatchTests(_FinalComposerTestCase):
    def test_five_projects_independently_reach_final_mp4_one_broken(self):
        project_ids = []
        for i in range(1, 5):
            project_ids.append(self._full_pipeline_project(f"Batch Final {i}", [f"Batch narration number {i}."]))

        # A fifth project deliberately has no Audio Master -- must fail in
        # isolation, without affecting the other four.
        from app.modules.beat.project_service import create_project

        with patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal):
            broken_project_id = create_project("Batch Final Broken", "placeholder", ProjectConfig())
        image = _make_solid_image(self.tmp_path / "broken_beat.jpg", (10, 200, 40))
        asset_id = self._register_image_asset(image)
        draft = get_project_draft(broken_project_id)
        beats = [Beat(id="b1", order=1, type=BeatType.BODY, narration="Broken.", duration=2.0, asset_id=asset_id)]
        broken_plan = BeatPlan(script_text=draft.script_text, beats=beats, project_name=draft.project_name, config=draft.config)
        update_project_beat_plan(broken_project_id, broken_plan)

        from app.modules.factory import service as factory_service

        results = {}
        for pid in project_ids:
            run, _created = factory_service.create_run(pid)
            draft = get_project_draft(pid)
            plan = BeatPlan(script_text=draft.script_text, beats=draft.beats, project_name=draft.project_name, config=draft.config)
            _stage_render(run.id, pid, plan, self.settings, self.service)
            after = self._get_run(run.id)
            job = self._wait_for_job(after.render_job_id)
            results[pid] = job.status

        run, _created = factory_service.create_run(broken_project_id)
        with self.assertRaises(FactoryStageError):
            _stage_render(run.id, broken_project_id, broken_plan, self.settings, self.service)

        self.assertTrue(all(status == "completed" for status in results.values()))
        for pid in project_ids:
            db = self._db()
            try:
                from app.modules.beat.models import Project

                project = db.get(Project, pid)
                self.assertIsNotNone(project.render_job_id)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
