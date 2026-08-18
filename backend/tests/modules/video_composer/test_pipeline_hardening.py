"""Tests for the Task 10 end-to-end pipeline hardening work (see
docs/features/37-e2e-pipeline-hardening.md): final output validation,
atomic output, the `.render/job_<id>/report.json` render report, external
API accounting, and debug-mode intermediate preservation.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob
from app.modules.video_composer.service import VideoComposerService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_clip(path: Path, duration: float, color: str, width: int, height: int, fps: float, with_audio: bool = True) -> Path:
    inputs = ["-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r={fps}"]
    maps = ["-pix_fmt", "yuv420p", "-c:v", "libx264"]
    if with_audio:
        inputs += ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={duration}"]
        maps += ["-c:a", "aac", "-shortest"]
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"] + inputs + maps + [str(path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class ValidateFinalOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_correct_output_passes_validation(self):
        clip = _make_clip(self.tmp_path / "good.mp4", 2.0, "red", 320, 568, 12.0)
        VideoComposerService._validate_final_output(clip, expected_duration=2.0, width=320, height=568, fps=12.0)

    def test_missing_file_raises_with_output_validation_failed_code(self):
        with self.assertRaises(RuntimeError) as ctx:
            VideoComposerService._validate_final_output(
                self.tmp_path / "nope.mp4", expected_duration=2.0, width=320, height=568, fps=12.0
            )
        self.assertIn("OUTPUT_VALIDATION_FAILED", str(ctx.exception))

    def test_wrong_resolution_raises(self):
        clip = _make_clip(self.tmp_path / "wrong_res.mp4", 2.0, "red", 320, 568, 12.0)
        with self.assertRaises(RuntimeError) as ctx:
            VideoComposerService._validate_final_output(clip, expected_duration=2.0, width=640, height=1136, fps=12.0)
        self.assertIn("OUTPUT_VALIDATION_FAILED", str(ctx.exception))

    def test_duration_outside_tolerance_raises(self):
        clip = _make_clip(self.tmp_path / "wrong_dur.mp4", 2.0, "red", 320, 568, 12.0)
        with self.assertRaises(RuntimeError) as ctx:
            VideoComposerService._validate_final_output(clip, expected_duration=10.0, width=320, height=568, fps=12.0)
        self.assertIn("OUTPUT_VALIDATION_FAILED", str(ctx.exception))

    def test_duration_within_tolerance_passes(self):
        clip = _make_clip(self.tmp_path / "close_dur.mp4", 2.0, "red", 320, 568, 12.0)
        # Real container/encoder rounding-sized difference, well within
        # _OUTPUT_DURATION_TOLERANCE_SEC (0.5s) -- must NOT raise.
        VideoComposerService._validate_final_output(clip, expected_duration=2.2, width=320, height=568, fps=12.0)

    def test_missing_audio_stream_raises(self):
        clip = _make_clip(self.tmp_path / "no_audio.mp4", 2.0, "red", 320, 568, 12.0, with_audio=False)
        with self.assertRaises(RuntimeError) as ctx:
            VideoComposerService._validate_final_output(clip, expected_duration=2.0, width=320, height=568, fps=12.0)
        # Task 26 (see docs/features/52-final-composer.md section 42) --
        # this check was tightened from "at least one audio stream" to
        # "exactly one," which also gave it its own, more specific code.
        self.assertIn("FINAL_STREAM_INVALID", str(ctx.exception))
        self.assertIn("audio", str(ctx.exception).lower())


class WriteRenderReportTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.library_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _report_path(self, job_id: int) -> Path:
        return self.library_dir / ".render" / f"job_{job_id}" / "report.json"

    def test_completed_report_local_narration_has_zero_cost(self):
        video = self.library_dir / "final.mp4"
        video.write_bytes(b"x" * 1024)
        VideoComposerService._write_render_report(
            self.library_dir, 1, status="completed", final_video=video, video_duration=6.0,
            clip_count=3, width=1080, height=1920, fps=30.0, caption_enabled=True,
            narration_mode="local", timing={"composition": 1.0, "audio": 0.5},
        )
        report = json.loads(self._report_path(1).read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["external_api_calls"], 0)
        self.assertEqual(report["external_api_cost_estimate"], 0)
        self.assertEqual(report["video"]["size_bytes"], 1024)
        self.assertEqual(report["beats"], 3)
        self.assertTrue(report["captions"])

    def test_completed_report_precomposed_narration_has_zero_cost(self):
        # Task 26 (see docs/features/52-final-composer.md) -- a real bug
        # caught by manual verification: this method originally treated any
        # narration_mode other than "local" as needing 1 external call,
        # mis-billing every precomposed (Factory Final Composer) render even
        # though narration/BGM/captions were all already produced locally.
        video = self.library_dir / "final.mp4"
        video.write_bytes(b"x" * 4096)
        VideoComposerService._write_render_report(
            self.library_dir, 4, status="completed", final_video=video, video_duration=6.0,
            clip_count=3, width=1080, height=1920, fps=30.0, caption_enabled=True,
            narration_mode="precomposed", timing={"composition": 1.0},
        )
        report = json.loads(self._report_path(4).read_text(encoding="utf-8"))
        self.assertEqual(report["external_api_calls"], 0)
        self.assertEqual(report["external_api_cost_estimate"], 0)

    def test_completed_report_tts_narration_reports_one_call_and_unknown_cost(self):
        video = self.library_dir / "final.mp4"
        video.write_bytes(b"x" * 2048)
        VideoComposerService._write_render_report(
            self.library_dir, 2, status="completed", final_video=video, video_duration=6.0,
            clip_count=1, width=1080, height=1920, fps=30.0, caption_enabled=False,
            narration_mode="tts", timing={},
        )
        report = json.loads(self._report_path(2).read_text(encoding="utf-8"))
        # edge_tts is a real external network call this pipeline makes, even
        # though it's free -- 1 call, honestly-unknown ($0 was never a
        # verified figure), not invented, per this task's own accounting
        # rules. See docs/features/37-e2e-pipeline-hardening.md.
        self.assertEqual(report["external_api_calls"], 1)
        self.assertIsNone(report["external_api_cost_estimate"])

    def test_failed_report_carries_error_code_and_phase(self):
        VideoComposerService._write_render_report(
            self.library_dir, 3, status="failed", error_code="RENDER_FAILED",
            error_message="ffmpeg exploded", failed_phase="merging", timing={"composition": None},
        )
        report = json.loads(self._report_path(3).read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error_code"], "RENDER_FAILED")
        self.assertEqual(report["failed_phase"], "merging")
        self.assertEqual(report["message"], "ffmpeg exploded")

    def test_report_lives_under_render_dir_independent_of_video_location(self):
        VideoComposerService._write_render_report(self.library_dir, 4, status="failed", failed_phase="finalizing")
        self.assertTrue((self.library_dir / ".render" / "job_4" / "report.json").exists())


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class RunJobHardeningIntegrationTests(unittest.TestCase):
    """Exercises the real, unmocked _run_job pipeline end to end (real
    ffmpeg, in-memory DB) to prove atomic output, the render report, and
    debug-mode intermediate preservation all work together, not just in
    isolation.
    """

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

        self.service = VideoComposerService(library_dir=self.tmp_path)
        self.clip = _make_clip(self.tmp_path / "clip.mp4", 1.0, "blue", 320, 568, 12.0)

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

    def test_successful_render_produces_atomic_output_no_leftover_tmp_and_full_report(self):
        job_id = self.service.create_job(
            title="Hardening test", script_text="", voice="en-US-GuyNeural", music_volume=0.15,
            transition_duration=0.2, burn_subtitles=True, requested_output_dir=None,
            narration_mode="local", beat_narration_specs=[{"duration": 1.0, "path": None}],
        )
        self.service.save_clip_paths(job_id, [self.clip])
        self.service._run_job(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        output_dir = Path(job.output_path).parent
        self.assertTrue(Path(job.output_path).exists())
        # Atomic output: the tmp write target must never survive a
        # successful render.
        self.assertFalse((output_dir / ".video_hoan_chinh.tmp.mp4").exists())

        report_path = self.tmp_path / ".render" / f"job_{job_id}" / "report.json"
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["external_api_calls"], 0)
        self.assertEqual(report["external_api_cost_estimate"], 0)
        for key in ("preflight", "beat_render", "composition", "audio", "captions", "validation", "total"):
            self.assertIn(key, report["timing"])

    def test_tmp_dir_is_cleaned_up_by_default_but_preserved_in_debug_mode(self):
        job_id = self.service.create_job(
            title="Debug mode test", script_text="", voice="en-US-GuyNeural", music_volume=0.15,
            transition_duration=0.2, burn_subtitles=True, requested_output_dir=None,
            narration_mode="local", beat_narration_specs=[{"duration": 1.0, "path": None}],
        )
        self.service.save_clip_paths(job_id, [self.clip])

        with patch("app.modules.video_composer.service.get_settings") as mock_settings:
            mock_settings.return_value.debug = True
            self.service._run_job(job_id)
        self.assertTrue((self.service.job_dir(job_id) / "tmp").exists())

    def test_default_mode_removes_tmp_dir_after_success(self):
        job_id = self.service.create_job(
            title="Cleanup test", script_text="", voice="en-US-GuyNeural", music_volume=0.15,
            transition_duration=0.2, burn_subtitles=True, requested_output_dir=None,
            narration_mode="local", beat_narration_specs=[{"duration": 1.0, "path": None}],
        )
        self.service.save_clip_paths(job_id, [self.clip])

        with patch("app.modules.video_composer.service.get_settings") as mock_settings:
            mock_settings.return_value.debug = False
            self.service._run_job(job_id)
        self.assertFalse((self.service.job_dir(job_id) / "tmp").exists())

    def test_failed_job_writes_failure_report_with_phase_and_code(self):
        corrupt_clip = self.tmp_path / "corrupt.mp4"
        corrupt_clip.write_bytes(b"not a real video")
        job_id = self.service.create_job(
            title="Failure report test", script_text="", voice="en-US-GuyNeural", music_volume=0.15,
            transition_duration=0.2, burn_subtitles=True, requested_output_dir=None,
            narration_mode="local", beat_narration_specs=[{"duration": 1.0, "path": None}],
        )
        self.service.save_clip_paths(job_id, [corrupt_clip])
        self.service._run_job(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "failed")

        report_path = self.tmp_path / ".render" / f"job_{job_id}" / "report.json"
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failed_phase"], "merging")
        self.assertEqual(report["error_code"], "RENDER_FAILED")


if __name__ == "__main__":
    unittest.main()
