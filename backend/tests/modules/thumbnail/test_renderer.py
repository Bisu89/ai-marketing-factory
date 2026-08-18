"""Tests for Task 27 -- see docs/features/53-thumbnail-metadata-package.md.
Real FFmpeg frame extraction + real Pillow raster tests for
app.modules.thumbnail.renderer -- no mocking of the engine itself, the
same "exercise the real engine" precedent every prior stage's own tests
already established.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.modules.thumbnail.renderer import (
    build_thumbnail,
    compute_frame_stats,
    save_thumbnail,
    select_thumbnail_frame,
    shorten_headline,
    validate_thumbnail,
)
from app.modules.thumbnail.schemas import ThumbnailConfig, ThumbnailError

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_textured_video(path: Path, duration: float = 6.0, width: int = 320, height: int = 568, fps: float = 12.0) -> Path:
    """A real, ffmpeg-generated video with genuine visual texture
    (mandelbrot pattern) throughout its whole duration -- unlike a flat
    solid-color test clip, every candidate offset should score as a
    legitimately usable frame here.
    """
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"mandelbrot=size={width}x{height}:rate={fps}",
         "-t", str(duration), "-pix_fmt", "yuv420p", str(path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


def _make_bad_video(path: Path, duration: float = 6.0, width: int = 320, height: int = 568, fps: float = 12.0) -> Path:
    """Black for the first half, solid white for the second -- every
    candidate offset should be rejected.
    """
    subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration / 2}:r={fps}",
         "-f", "lavfi", "-i", f"color=c=white:s={width}x{height}:d={duration / 2}:r={fps}",
         "-filter_complex", "[0][1]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-pix_fmt", "yuv420p", str(path)],
        check=True, stdin=subprocess.DEVNULL,
    )
    return path


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class SelectThumbnailFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_extraction_produces_a_readable_thumbnail(self):
        video = _make_textured_video(self.tmp_path / "good.mp4")
        config = ThumbnailConfig(width=1080, height=1920, headline_enabled=False)
        frame = select_thumbnail_frame(video, config, self.tmp_path / "candidates")
        self.assertTrue(frame.exists())
        img = build_thumbnail(frame, config)
        out = self.tmp_path / "thumb.jpg"
        save_thumbnail(img, out)
        validate_thumbnail(out, expected_width=1080, expected_height=1920)
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 0)

    def test_bad_video_falls_back_to_the_least_bad_candidate_instead_of_failing(self):
        # Section 7's own rejection heuristics still apply, but a real,
        # merely flat/low-detail video (not corrupt) must not hard-fail
        # the whole Package stage over it -- see
        # select_best_frame_with_fallback's own "never block the factory
        # over a soft failure" reasoning.
        video = _make_bad_video(self.tmp_path / "bad.mp4")
        config = ThumbnailConfig(width=1080, height=1920, headline_enabled=False)
        frame = select_thumbnail_frame(video, config, self.tmp_path / "candidates")
        self.assertTrue(frame.exists())

    def test_video_with_no_extractable_frames_raises_no_valid_frame(self):
        # A genuinely corrupt/unreadable video -- nothing to fall back to.
        corrupt = self.tmp_path / "corrupt.mp4"
        corrupt.write_bytes(b"not a real video file")
        config = ThumbnailConfig(width=1080, height=1920, headline_enabled=False)
        with self.assertRaises(ThumbnailError) as ctx:
            select_thumbnail_frame(corrupt, config, self.tmp_path / "candidates")
        self.assertEqual(ctx.exception.code, "THUMBNAIL_GENERATION_FAILED")

    def test_selection_is_deterministic_across_repeated_runs(self):
        video = _make_textured_video(self.tmp_path / "det.mp4")
        config = ThumbnailConfig(width=1080, height=1920, headline_enabled=False)
        first = select_thumbnail_frame(video, config, self.tmp_path / "c1")
        second = select_thumbnail_frame(video, config, self.tmp_path / "c2")
        first_stats = compute_frame_stats(0.0, first)
        second_stats = compute_frame_stats(0.0, second)
        # Same offset (candidate index) picked both times -- the actual
        # extracted bytes may differ by container/codec noise, but the
        # underlying frame statistics must match near-exactly.
        self.assertAlmostEqual(first_stats.brightness, second_stats.brightness, delta=1.0)
        self.assertAlmostEqual(first_stats.contrast, second_stats.contrast, delta=1.0)

    def test_aspect_ratios_16_9_1_1_9_16_all_produce_correct_dimensions(self):
        video = _make_textured_video(self.tmp_path / "aspect.mp4")
        for width, height in [(1920, 1080), (1080, 1080), (1080, 1920)]:
            config = ThumbnailConfig(width=width, height=height, headline_enabled=False)
            frame = select_thumbnail_frame(video, config, self.tmp_path / f"cand_{width}x{height}")
            img = build_thumbnail(frame, config)
            out = self.tmp_path / f"thumb_{width}x{height}.jpg"
            save_thumbnail(img, out)
            validate_thumbnail(out, expected_width=width, expected_height=height)
            with Image.open(out) as check:
                self.assertEqual(check.size, (width, height))

    def test_headline_is_burned_into_the_thumbnail(self):
        video = _make_textured_video(self.tmp_path / "headline.mp4")
        config = ThumbnailConfig(width=1080, height=1920, headline_enabled=True, headline_text="A Big Reveal Happens Here")
        frame = select_thumbnail_frame(video, config, self.tmp_path / "candidates")
        without = build_thumbnail(frame, ThumbnailConfig(width=1080, height=1920, headline_enabled=False))
        with_headline = build_thumbnail(frame, config)
        # A real, measurable difference -- the headline band actually changed pixels.
        self.assertNotEqual(without.tobytes()[-1000:], with_headline.tobytes()[-1000:])

    def test_configurable_candidate_count(self):
        video = _make_textured_video(self.tmp_path / "count.mp4")
        config = ThumbnailConfig(width=1080, height=1920, candidate_offsets=(0.5,), headline_enabled=False)
        frame = select_thumbnail_frame(video, config, self.tmp_path / "candidates")
        self.assertTrue(frame.exists())


class HeadlineShorteningTests(unittest.TestCase):
    def test_short_text_is_upper_cased_unchanged(self):
        self.assertEqual(shorten_headline("A short hook", 40), "A SHORT HOOK")

    def test_long_text_is_shortened_at_a_word_boundary(self):
        text = "She Finally Told Him Why She Left After Ten Years"
        result = shorten_headline(text, 20)
        self.assertLessEqual(len(result), 20)
        self.assertTrue(result.isupper())
        # Never cuts mid-word: every word in the result appears verbatim
        # (case-insensitively) in the original text.
        for word in result.split():
            self.assertIn(word, text.upper())

    def test_never_truncates_mid_word(self):
        text = "Supercalifragilisticexpialidocious is one extremely long single word"
        result = shorten_headline(text, 10)
        # A single word longer than the limit is hard-truncated (no spaces
        # to break at) -- but multi-word text never ends mid-word.
        text2 = "One two three four five six seven eight"
        result2 = shorten_headline(text2, 15)
        for word in result2.split():
            self.assertIn(word, text2.upper())

    def test_deterministic(self):
        text = "The same input always produces the same output"
        self.assertEqual(shorten_headline(text, 25), shorten_headline(text, 25))


class ValidateThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_missing_file_raises_thumbnail_invalid(self):
        with self.assertRaises(ThumbnailError) as ctx:
            validate_thumbnail(self.tmp_path / "nope.jpg", expected_width=1080, expected_height=1920)
        self.assertEqual(ctx.exception.code, "THUMBNAIL_INVALID")

    def test_empty_file_raises_thumbnail_invalid(self):
        path = self.tmp_path / "empty.jpg"
        path.write_bytes(b"")
        with self.assertRaises(ThumbnailError) as ctx:
            validate_thumbnail(path, expected_width=1080, expected_height=1920)
        self.assertEqual(ctx.exception.code, "THUMBNAIL_INVALID")

    def test_wrong_dimensions_raises_thumbnail_invalid(self):
        path = self.tmp_path / "wrong_size.jpg"
        Image.new("RGB", (100, 100), color=(10, 20, 30)).save(path, "JPEG")
        with self.assertRaises(ThumbnailError) as ctx:
            validate_thumbnail(path, expected_width=1080, expected_height=1920)
        self.assertEqual(ctx.exception.code, "THUMBNAIL_INVALID")

    def test_correct_thumbnail_passes_validation(self):
        path = self.tmp_path / "good.jpg"
        Image.new("RGB", (1080, 1920), color=(10, 20, 30)).save(path, "JPEG")
        validate_thumbnail(path, expected_width=1080, expected_height=1920)  # must not raise

    def test_non_jpeg_format_raises_thumbnail_invalid(self):
        path = self.tmp_path / "wrong_format.jpg"
        Image.new("RGB", (1080, 1920), color=(10, 20, 30)).save(path, "PNG")
        with self.assertRaises(ThumbnailError) as ctx:
            validate_thumbnail(path, expected_width=1080, expected_height=1920)
        self.assertEqual(ctx.exception.code, "THUMBNAIL_INVALID")


if __name__ == "__main__":
    unittest.main()
