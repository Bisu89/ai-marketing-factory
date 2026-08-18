"""Tests for app.modules.postqa.renderer (Task 28 -- see
docs/features/54-final-qa.md). Real ffmpeg/ffprobe/Pillow I/O -- no
mocking of the engine itself, the same "exercise the real engine"
precedent every prior stage's own tests already established (see e.g.
tests.modules.thumbnail.test_renderer).
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.modules.postqa.renderer import (
    parse_ass_captions,
    probe_audio_levels,
    probe_final_video,
    probe_thumbnail_dimensions,
    thumbnail_looks_low_quality,
)

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_video_with_tone(path: Path, duration: float = 3.0, width: int = 320, height: int = 240, fps: float = 24.0) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=blue:s={width}x{height}:d={duration}:r={fps}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


def _make_silent_video(path: Path, duration: float = 2.0, width: int = 320, height: int = 240, fps: float = 24.0) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=red:s={width}x{height}:d={duration}:r={fps}",
         "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
         "-t", str(duration), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-c:a", "aac", str(path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


def _make_solid_jpeg(path: Path, color=(80, 80, 80), size=(320, 320)) -> Path:
    Image.new("RGB", size, color).save(path, "JPEG")
    return path


def _make_textured_jpeg(path: Path, size=(320, 320)) -> Path:
    img = Image.new("RGB", size)
    pixels = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            pixels[x, y] = ((x * 3) % 256, (y * 5) % 256, ((x + y) * 2) % 256)
    img.save(path, "JPEG")
    return path


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class ProbeFinalVideoTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_real_video_reports_correct_streams_and_dimensions(self):
        video = _make_video_with_tone(self.tmp_path / "video.mp4", duration=3.0, width=320, height=240, fps=24.0)
        info = probe_final_video(video)
        self.assertTrue(info.file_exists)
        self.assertEqual(info.video_streams, 1)
        self.assertEqual(info.audio_streams, 1)
        self.assertEqual(info.width, 320)
        self.assertEqual(info.height, 240)
        self.assertAlmostEqual(info.fps, 24.0, delta=0.5)
        self.assertAlmostEqual(info.duration, 3.0, delta=0.5)
        self.assertEqual(info.video_codec, "h264")
        self.assertEqual(info.audio_codec, "aac")
        self.assertGreater(info.file_size, 0)

    def test_missing_file_reports_file_exists_false_never_raises(self):
        info = probe_final_video(self.tmp_path / "nope.mp4")
        self.assertFalse(info.file_exists)
        self.assertEqual(info.video_streams, 0)
        self.assertEqual(info.duration, 0.0)

    def test_non_video_file_reports_file_exists_true_but_zero_streams(self):
        garbage = self.tmp_path / "not_a_video.mp4"
        garbage.write_bytes(b"this is not a real video file")
        info = probe_final_video(garbage)
        self.assertTrue(info.file_exists)
        self.assertEqual(info.video_streams, 0)
        self.assertEqual(info.audio_streams, 0)


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class ProbeAudioLevelsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_real_tone_reports_audible_non_silent_levels(self):
        video = _make_video_with_tone(self.tmp_path / "tone.mp4")
        level = probe_audio_levels(video)
        self.assertTrue(level.probed)
        self.assertIsNotNone(level.mean_volume_db)
        self.assertGreater(level.mean_volume_db, -50.0)

    def test_true_silence_reports_very_low_mean_volume(self):
        video = _make_silent_video(self.tmp_path / "silent.mp4")
        level = probe_audio_levels(video)
        self.assertTrue(level.probed)
        self.assertIsNotNone(level.mean_volume_db)
        self.assertLessEqual(level.mean_volume_db, -50.0)

    def test_missing_file_reports_unprobed(self):
        level = probe_audio_levels(self.tmp_path / "nope.mp4")
        self.assertFalse(level.probed)
        self.assertIsNone(level.mean_volume_db)


class ParseAssCaptionsTests(unittest.TestCase):
    def test_counts_dialogue_lines_and_finds_max_end_time(self):
        content = (
            "[Script Info]\nScriptType: v4.00+\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:02.50,Default,,0,0,0,,Hello there\n"
            "Dialogue: 0,0:00:02.50,0:00:05.20,Default,,0,0,0,,Second line\n"
        )
        count, max_end = parse_ass_captions(content)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(max_end, 5.2, places=2)

    def test_empty_text_dialogue_lines_are_not_counted(self):
        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,\n"
        )
        count, max_end = parse_ass_captions(content)
        self.assertEqual(count, 0)
        self.assertIsNone(max_end)

    def test_no_dialogue_lines_returns_zero_and_none(self):
        count, max_end = parse_ass_captions("[Script Info]\nScriptType: v4.00+\n")
        self.assertEqual(count, 0)
        self.assertIsNone(max_end)

    def test_hour_boundary_time_parses_correctly(self):
        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,1:00:05.25,Default,,0,0,0,,Long one\n"
        )
        count, max_end = parse_ass_captions(content)
        self.assertEqual(count, 1)
        self.assertAlmostEqual(max_end, 3605.25, places=2)


class ThumbnailQualityRecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_textured_midtone_image_is_not_low_quality(self):
        img = _make_textured_jpeg(self.tmp_path / "good.jpg")
        self.assertFalse(thumbnail_looks_low_quality(img))

    def test_near_black_image_is_low_quality(self):
        img = _make_solid_jpeg(self.tmp_path / "black.jpg", color=(2, 2, 2))
        self.assertTrue(thumbnail_looks_low_quality(img))

    def test_near_white_image_is_low_quality(self):
        img = _make_solid_jpeg(self.tmp_path / "white.jpg", color=(253, 253, 253))
        self.assertTrue(thumbnail_looks_low_quality(img))

    def test_flat_midtone_image_is_low_quality(self):
        img = _make_solid_jpeg(self.tmp_path / "flat.jpg", color=(128, 128, 128))
        self.assertTrue(thumbnail_looks_low_quality(img))

    def test_missing_file_is_not_reported_low_quality_here(self):
        # Section -- the caller's own exists/size check owns "missing," not
        # this function -- see this module's own docstring.
        self.assertFalse(thumbnail_looks_low_quality(self.tmp_path / "nope.jpg"))


class ProbeThumbnailDimensionsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_real_image_reports_correct_dimensions(self):
        img = _make_solid_jpeg(self.tmp_path / "img.jpg", size=(640, 360))
        self.assertEqual(probe_thumbnail_dimensions(img), (640, 360))

    def test_missing_file_returns_none(self):
        self.assertIsNone(probe_thumbnail_dimensions(self.tmp_path / "nope.jpg"))

    def test_corrupt_file_returns_none(self):
        bad = self.tmp_path / "corrupt.jpg"
        bad.write_bytes(b"not a real jpeg")
        self.assertIsNone(probe_thumbnail_dimensions(bad))


if __name__ == "__main__":
    unittest.main()
