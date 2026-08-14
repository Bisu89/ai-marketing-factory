"""Tests for the local (non-TTS) audio pipeline added in
docs/features/36-audio-pipeline.md: VideoComposerService._build_narration_timeline
(per-beat narration timeline building) and its integration into _run_job's
narration_mode="local" path -- narration + background music mixed into a
real final.mp4, entirely offline (no edge_tts / no external API call).
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import selectinload, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob
from app.modules.video_composer.service import VideoComposerService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return float(result.stdout.strip())


def _mean_volume_db(path: Path, start: float, duration: float) -> float:
    result = subprocess.run(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-i", str(path),
            "-af", f"atrim=start={start}:duration={duration},volumedetect",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", result.stderr)
    assert match, f"volumedetect produced no mean_volume in stderr: {result.stderr}"
    return float(match.group(1))


def _make_tone(path: Path, frequency: int, duration: float) -> Path:
    subprocess.run(
        [
            "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={duration}",
            "-c:a", "libmp3lame", str(path),
        ],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


def _make_solid_video(path: Path, duration: float, color: str, width: int, height: int, fps: float) -> Path:
    subprocess.run(
        [
            "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
            "-pix_fmt", "yuv420p", str(path),
        ],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class BuildNarrationTimelineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_total_duration_matches_sum_of_beat_durations(self):
        tone = _make_tone(self.tmp_path / "n.mp3", 440, 1.0)
        specs = [
            {"duration": 2.0, "path": str(tone)},
            {"duration": 1.5, "path": None},
            {"duration": 2.5, "path": str(tone)},
        ]
        output = self.tmp_path / "timeline.m4a"
        VideoComposerService._build_narration_timeline(specs, self.tmp_path / "segments", output)

        self.assertTrue(output.exists())
        self.assertAlmostEqual(_ffprobe_duration(output), 6.0, delta=0.2)

    def test_concat_list_uses_absolute_paths(self):
        # Regression test for a real bug (see
        # docs/features/36-audio-pipeline.md): ffmpeg's concat demuxer
        # resolves relative "file" entries against the *list file's own
        # directory*, not the process's cwd. This app's default library_dir
        # is itself a relative path ("./data/library"), so a segment path
        # built from it was already relative -- writing that straight into
        # concat.txt (which lives inside that same relative tree) doubled
        # the path and made ffmpeg fail to find its own just-created
        # segments. Segment paths in concat.txt must always be absolute,
        # regardless of whether segments_dir/output_path were given as
        # relative or absolute paths by the caller.
        tone = _make_tone(self.tmp_path / "n.mp3", 440, 1.0)
        specs = [{"duration": 1.0, "path": str(tone)}]
        segments_dir = self.tmp_path / "segments"
        output = self.tmp_path / "timeline.m4a"
        VideoComposerService._build_narration_timeline(specs, segments_dir, output)

        concat_text = (segments_dir / "concat.txt").read_text(encoding="utf-8")
        for line in concat_text.splitlines():
            file_path = line.removeprefix("file '").removesuffix("'")
            self.assertTrue(Path(file_path).is_absolute(), f"concat.txt entry is not absolute: {line!r}")

    def test_narration_shorter_than_beat_is_padded_with_trailing_silence(self):
        tone = _make_tone(self.tmp_path / "n.mp3", 440, 1.0)  # 1s of tone
        specs = [{"duration": 3.0, "path": str(tone)}]  # beat is 3s
        output = self.tmp_path / "timeline.m4a"
        VideoComposerService._build_narration_timeline(specs, self.tmp_path / "segments", output)

        self.assertAlmostEqual(_ffprobe_duration(output), 3.0, delta=0.15)
        # First ~0.8s: audible tone.
        self.assertGreater(_mean_volume_db(output, start=0.0, duration=0.8), -50)
        # Last ~0.8s: padded silence.
        self.assertLess(_mean_volume_db(output, start=2.1, duration=0.8), -50)

    def test_beat_with_no_narration_asset_is_pure_silence_for_its_full_duration(self):
        specs = [{"duration": 2.0, "path": None}]
        output = self.tmp_path / "timeline.m4a"
        VideoComposerService._build_narration_timeline(specs, self.tmp_path / "segments", output)

        self.assertAlmostEqual(_ffprobe_duration(output), 2.0, delta=0.15)
        self.assertLess(_mean_volume_db(output, start=0.0, duration=1.8), -50)

    def test_narration_gap_does_not_shift_a_later_beats_narration(self):
        # Beat 1: narration. Beat 2: silence (no asset). Beat 3: narration.
        # The gap must land exactly where beat 2 is, not be skipped over.
        tone = _make_tone(self.tmp_path / "n.mp3", 440, 1.0)
        specs = [
            {"duration": 2.0, "path": str(tone)},
            {"duration": 2.0, "path": None},
            {"duration": 2.0, "path": str(tone)},
        ]
        output = self.tmp_path / "timeline.m4a"
        VideoComposerService._build_narration_timeline(specs, self.tmp_path / "segments", output)

        self.assertAlmostEqual(_ffprobe_duration(output), 6.0, delta=0.2)
        # Beat 2's window (2.0s-4.0s) must be silent.
        self.assertLess(_mean_volume_db(output, start=2.2, duration=1.5), -50)
        # Beat 3's window (4.0s-6.0s) must have the tone again.
        self.assertGreater(_mean_volume_db(output, start=4.0, duration=0.8), -50)

    def test_beats_preserve_order_not_just_total_duration(self):
        # A silence-then-tone timeline must sound different from a
        # tone-then-silence one, even though both sum to the same duration
        # -- proves order is respected, not just total length.
        tone = _make_tone(self.tmp_path / "n.mp3", 440, 1.0)
        specs = [{"duration": 1.0, "path": None}, {"duration": 1.0, "path": str(tone)}]
        output = self.tmp_path / "timeline.m4a"
        VideoComposerService._build_narration_timeline(specs, self.tmp_path / "segments", output)

        self.assertLess(_mean_volume_db(output, start=0.0, duration=0.7), -50)
        self.assertGreater(_mean_volume_db(output, start=1.0, duration=0.7), -50)


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class LocalNarrationRenderIntegrationTests(unittest.TestCase):
    """The task's own literal scenario: 3 beats, 2 seconds each, local
    narration, local music -- rendered end to end with zero external API
    calls (no edge_tts patch needed at all in local mode, unlike every
    other render test in this codebase).
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

    def test_three_beats_local_narration_and_music_render_to_a_valid_final_mp4(self):
        clip_paths = [
            _make_solid_video(self.tmp_path / f"beat_{i}.mp4", 2.0, color, 320, 568, 12.0)
            for i, color in enumerate(["red", "green", "blue"])
        ]
        narration = _make_tone(self.tmp_path / "narration.mp3", 440, 1.0)
        music = _make_tone(self.tmp_path / "music.mp3", 220, 3.0)  # shorter than the 6s video -- must loop

        job_id = self.service.create_job(
            title="Local audio pipeline test",
            script_text="",
            voice="en-US-GuyNeural",
            music_volume=0.15,
            transition_duration=0.2,
            burn_subtitles=True,
            requested_output_dir=None,
            music_ducking_ratio=8.0,
            fade_out_sec=0.5,
            narration_mode="local",
            beat_narration_specs=[
                {"duration": 2.0, "path": str(narration)},
                {"duration": 2.0, "path": None},  # beat 2: no narration -- silence
                {"duration": 2.0, "path": str(narration)},
            ],
        )
        self.service.save_clip_paths(job_id, clip_paths)
        self.service.set_music_path(job_id, str(music))

        # No edge_tts patch here -- local mode never calls it. If this test
        # somehow did reach _run_narration, it would hang/fail on a real
        # network call, which is exactly what proves narration_mode="local"
        # genuinely skips TTS.
        self.service._run_job(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        self.assertEqual(job.narration_mode, "local")
        output_path = Path(job.output_path)
        self.assertTrue(output_path.exists())

        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_type,codec_name",
                "-show_entries", "format=duration",
                "-of", "json", str(output_path),
            ],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        data = json.loads(probe.stdout)
        video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
        audio_stream = next(s for s in data["streams"] if s["codec_type"] == "audio")

        self.assertEqual(video_stream["codec_name"], "h264")
        self.assertEqual(audio_stream["codec_name"], "aac")
        # 3x 2s clips, two 0.2s crossfades: 2.0 + (2.0-0.2)*2 = 5.6s
        self.assertAlmostEqual(float(data["format"]["duration"]), 5.6, delta=0.3)


if __name__ == "__main__":
    unittest.main()
