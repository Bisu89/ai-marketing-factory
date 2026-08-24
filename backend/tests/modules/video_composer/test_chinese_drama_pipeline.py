"""Real, end-to-end pipeline tests for Chinese Drama -> Vietnamese Shorts
(source_language set on a VideoComposeJob) -- real ffmpeg cover-crop, real
edge-tts WordBoundary narration/captions, real final encode. Only the
injected `dub_generator` (ASR + LLM) is faked, matching this suite's own
"exercise the real engine, mock external network AI calls" precedent (see
tests/api/test_chinese_drama_dub.py's docstring for the ASR/LLM-level unit
tests this file does not repeat).
"""

import shutil
import subprocess
import tempfile
import time
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

_WAIT_TIMEOUT_SEC = 60.0
_POLL_SEC = 0.1


def _make_landscape_clip(path: Path, duration: float = 2.0, size: str = "1280x720") -> Path:
    """A real, genuinely landscape (16:9) source clip with visual texture --
    the whole point of this mode's cover-crop step is converting exactly
    this kind of footage into a vertical short.
    """
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"mandelbrot=size={size}:rate=10",
         "-t", str(duration), "-pix_fmt", "yuv420p", str(path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


class _FakeDubResult:
    def __init__(self, translation: str, title: str, hook: str):
        self.translation = translation
        self.title = title
        self.hook = hook


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class ChineseDramaPipelineTests(unittest.TestCase):
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

        self.dub_calls: list[Path] = []
        self.fake_dub_result = _FakeDubResult(
            translation="Xin chào các bạn, đây là một câu chuyện rất thú vị.",
            title="Cô ấy phát hiện bí mật động trời của chồng",
            hook="Điều gì đã xảy ra?",
        )

        def fake_dub_generator(video_path: Path, on_transcribed) -> _FakeDubResult:
            self.dub_calls.append(video_path)
            on_transcribed()
            return self.fake_dub_result

        self.fake_dub_generator = fake_dub_generator
        self.service = VideoComposerService(library_dir=self.tmp_path, dub_generator=fake_dub_generator)
        self.service.start()

    def tearDown(self):
        self.service.shutdown()
        self.session_patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _get_job(self, job_id: int) -> VideoComposeJob:
        db = self.TestSessionLocal()
        try:
            return db.query(VideoComposeJob).filter(VideoComposeJob.id == job_id).first()
        finally:
            db.close()

    def _wait_terminal(self, job_id: int, timeout: float = _WAIT_TIMEOUT_SEC) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self._get_job(job_id).status
            if status in ("completed", "failed", "cancelled"):
                return status
            time.sleep(_POLL_SEC)
        self.fail("Timed out waiting for job to reach a terminal status")

    def _create_dub_job(self) -> int:
        job_id = self.service.create_job(
            title="(pending translation)", script_text="(pending translation)", voice="vi-VN-HoaiMyNeural",
            narration_rate="+5%", music_volume=0.15, transition_duration=0.5, burn_subtitles=True,
            requested_output_dir=None, render_profile="SOCIAL_VERTICAL", source_language="zh",
        )
        clip = _make_landscape_clip(self.tmp_path / "source.mp4")
        self.service.save_input_clips(job_id, [("source.mp4", open(clip, "rb"))])
        self.service.enqueue(job_id)
        return job_id

    def test_full_pipeline_produces_translated_metadata_and_vertical_output(self):
        job_id = self._create_dub_job()
        status = self._wait_terminal(job_id)
        self.assertEqual(status, "completed")

        job = self._get_job(job_id)
        self.assertEqual(job.title, self.fake_dub_result.title)
        self.assertEqual(job.script_text, self.fake_dub_result.translation)
        self.assertEqual(job.hook_text, self.fake_dub_result.hook)
        self.assertEqual(len(self.dub_calls), 1)

        # Cover-crop actually ran: a 1280x720 landscape source became a
        # real vertical SOCIAL_VERTICAL (1080x1920) output.
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", job.output_path],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        width_str, height_str = probe.stdout.strip().split("x")
        self.assertEqual((int(width_str), int(height_str)), (1080, 1920))

        # Real captions were burned from real edge-tts WordBoundary timing
        # (not the mocked ASR/LLM text -- the SRT/ASS pipeline is entirely
        # unmodified/real downstream of the translation).
        self.assertTrue(job.subtitle_srt_path)
        self.assertTrue(Path(job.subtitle_srt_path).exists())
        self.assertGreater(Path(job.subtitle_srt_path).stat().st_size, 0)

    def test_retry_does_not_re_call_dub_generator(self):
        job_id = self._create_dub_job()
        self._wait_terminal(job_id)
        self.assertEqual(len(self.dub_calls), 1)

        self.service._set_status(job_id, "failed")  # simulate a downstream failure for retry purposes
        new_job_id = self.service.retry_job(job_id)
        self._wait_terminal(new_job_id)

        # The already-translated title/script_text/hook_text were copied
        # onto the new job at retry time -- dub_generator must never be
        # called a second time for the same (unchanged) source video.
        self.assertEqual(len(self.dub_calls), 1)
        retried = self._get_job(new_job_id)
        self.assertEqual(retried.title, self.fake_dub_result.title)
        self.assertEqual(retried.script_text, self.fake_dub_result.translation)

    def test_classic_job_without_source_language_never_calls_dub_generator(self):
        """Regression guard: existing modes must work exactly as before."""
        job_id = self.service.create_job(
            title="Classic Upload", script_text="Hello world, this is a classic upload job.",
            voice="en-US-GuyNeural", music_volume=0.15, transition_duration=0.5, burn_subtitles=True,
            requested_output_dir=None,
        )
        clip = _make_landscape_clip(self.tmp_path / "classic.mp4")
        self.service.save_input_clips(job_id, [("classic.mp4", open(clip, "rb"))])
        self.service.enqueue(job_id)
        status = self._wait_terminal(job_id)

        self.assertEqual(status, "completed")
        self.assertEqual(self.dub_calls, [])
        job = self._get_job(job_id)
        self.assertEqual(job.title, "Classic Upload")
        # No cover-crop for a classic job -- single-clip fast path keeps
        # the source's own original 1280x720 dimensions untouched.
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", job.output_path],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        width_str, height_str = probe.stdout.strip().split("x")
        self.assertEqual((int(width_str), int(height_str)), (1280, 720))


if __name__ == "__main__":
    unittest.main()
