"""Real-ffmpeg tests for StorytellerService._composite -- background loop
(file or generated colour), avatar colour-key overlay, burned captions.
Mirrors the "exercise the real engine" precedent (tests/modules/video_composer).
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.modules.storyteller.service import (
    StorytellerService,
    _probe_duration,
    _probe_video_info,
    _run_ffmpeg,
    _sample_corner_color,
    _write_captions,
)

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _silent_audio(path: Path, duration: float) -> None:
    _run_ffmpeg(["-f", "lavfi", "-t", str(duration), "-i", "anullsrc=r=44100:cl=mono", "-c:a", "libmp3lame", str(path)])


def _solid_clip(path: Path, color: str, size: str, duration: float = 2.0) -> None:
    _run_ffmpeg([
        "-f", "lavfi", "-t", str(duration), "-i", f"color=c={color}:s={size}:rate=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ])


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class CompositeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.dispose() if hasattr(self.tmp, "dispose") else self.tmp.cleanup()

    def test_generated_background_no_avatar_no_captions(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 3.0)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=3.0, narration_path=narration, background_path=None, avatar_path=None,
            avatar_key_color=None, captions_path=None, output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))
        self.assertAlmostEqual(_probe_duration(out), 3.0, delta=0.3)

    def test_file_background_is_scaled_and_cropped_to_output_size(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.0)
        bg = self.tmp_path / "bg.mp4"
        _solid_clip(bg, "navy", "640x360", duration=1.0)  # smaller + wrong AR than output
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=2.0, narration_path=narration, background_path=bg, avatar_path=None,
            avatar_key_color=None, captions_path=None, output_path=out,
        )
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))

    def test_avatar_colorkey_overlay_and_captions_together(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.0)
        avatar = self.tmp_path / "avatar.mp4"
        _solid_clip(avatar, "green", "300x500", duration=1.0)
        key_color = _sample_corner_color(avatar, self.tmp_path)
        self.assertRegex(key_color, r"^0x[0-9A-Fa-f]{6}$")

        captions = self.tmp_path / "captions.ass"
        _write_captions([{"text": "xin", "start": 0.0, "end": 0.3}, {"text": "chao", "start": 0.3, "end": 0.6}], captions)
        self.assertIn("Dialogue:", captions.read_text(encoding="utf-8"))

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=2.0, narration_path=narration, background_path=None, avatar_path=avatar,
            avatar_key_color=key_color, captions_path=captions, output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))

    def test_still_image_background_is_looped_for_the_full_duration(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.5)
        bg = self.tmp_path / "bg.png"
        Image.new("RGB", (800, 600), color=(20, 60, 120)).save(bg)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=2.5, narration_path=narration, background_path=bg, background_is_image=True,
            avatar_path=None, avatar_key_color=None, captions_path=None, output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))
        self.assertAlmostEqual(_probe_duration(out), 2.5, delta=0.3)

    def test_still_image_avatar_colorkey_overlay(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.0)
        avatar = self.tmp_path / "avatar.png"
        img = Image.new("RGB", (300, 500), color=(0, 255, 0))
        img.save(avatar)
        key_color = _sample_corner_color(avatar, self.tmp_path)
        self.assertEqual(key_color, "0x00FF00")

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=2.0, narration_path=narration, background_path=None, avatar_path=avatar,
            avatar_is_image=True, avatar_key_color=key_color, captions_path=None, output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))

    def test_output_duration_matches_requested_duration_even_if_inputs_are_longer(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 5.0)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=1.5, narration_path=narration, background_path=None, avatar_path=None,
            avatar_key_color=None, captions_path=None, output_path=out,
        )
        self.assertAlmostEqual(_probe_duration(out), 1.5, delta=0.3)


if __name__ == "__main__":
    unittest.main()
