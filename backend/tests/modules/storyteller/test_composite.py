"""Real-ffmpeg tests for StorytellerService._composite -- "single" layout
(background loop/still-image + avatar colour-key overlay), "triptych"
layout (3-panel split), "slideshow" layout (many images, one beat + random
Ken Burns zoom each), burned captions, disclaimer + story-info overlays.
Mirrors the "exercise the real engine" precedent (tests/modules/video_composer).
"""

import random
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.modules.storyteller.service import (
    StorytellerService,
    _Panel,
    _mix_narration_and_music,
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
class SingleLayoutCompositeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generated_background_no_avatar_no_captions(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 3.0)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(duration=3.0, narration_path=narration, output_path=out)
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
            duration=2.0, narration_path=narration, background=_Panel(bg, False), output_path=out,
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
            duration=2.0, narration_path=narration, avatar=_Panel(avatar, False, key_color),
            captions_path=captions, output_path=out,
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
            duration=2.5, narration_path=narration, background=_Panel(bg, True), output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))
        self.assertAlmostEqual(_probe_duration(out), 2.5, delta=0.3)

    def test_still_image_avatar_colorkey_overlay(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.0)
        avatar = self.tmp_path / "avatar.png"
        Image.new("RGB", (300, 500), color=(0, 255, 0)).save(avatar)
        key_color = _sample_corner_color(avatar, self.tmp_path)
        self.assertEqual(key_color, "0x00FF00")

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=2.0, narration_path=narration, avatar=_Panel(avatar, True, key_color), output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))

    def test_output_duration_matches_requested_duration_even_if_inputs_are_longer(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 5.0)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(duration=1.5, narration_path=narration, output_path=out)
        self.assertAlmostEqual(_probe_duration(out), 1.5, delta=0.3)

    def test_disclaimer_and_story_info_card_render_without_error(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.0)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=2.0, narration_path=narration, output_path=out,
            disclaimer_text="Nội dung chỉ mang tính giải trí.",
            info_lines=["Truyện: Test", "Tác giả: Ai đó", "Nhân vật chính: A"],
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))

    def test_disclaimer_text_with_special_characters_does_not_break_ffmpeg(self):
        # colons/quotes/percent are drawtext-filter-graph metacharacters --
        # must be escaped, not just passed through.
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 1.5)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=1.5, narration_path=narration, output_path=out,
            disclaimer_text="Cảnh báo: 100% giải trí, 'không' áp dụng!",
        )
        self.assertTrue(out.exists())


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class TriptychLayoutCompositeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_three_generated_panels_hstack_to_full_output_size(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.0)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=2.0, narration_path=narration, layout="triptych", output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))

    def test_three_real_clips_of_different_sizes_hstack_cleanly(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 1.5)
        left = self.tmp_path / "left.mp4"
        middle = self.tmp_path / "middle.png"
        right = self.tmp_path / "right.mp4"
        _solid_clip(left, "red", "400x700", duration=1.0)
        Image.new("RGB", (1000, 500), color=(10, 200, 10)).save(middle)
        _solid_clip(right, "blue", "1920x1080", duration=1.0)

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=1.5, narration_path=narration, layout="triptych",
            left=_Panel(left, False), middle=_Panel(middle, True), right=_Panel(right, False),
            output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))
        self.assertAlmostEqual(_probe_duration(out), 1.5, delta=0.3)

    def test_triptych_with_captions_and_overlays_together(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 1.5)
        captions = self.tmp_path / "captions.ass"
        _write_captions([{"text": "xin", "start": 0.0, "end": 0.3}], captions)

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=1.5, narration_path=narration, layout="triptych", captions_path=captions,
            disclaimer_text="Giải trí, không phản ánh thực tế.",
            info_lines=["Truyện: X", "Tác giả: Y"],
            output_path=out,
        )
        self.assertTrue(out.exists())


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class SlideshowLayoutCompositeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generated_images_concat_to_full_duration_and_output_size(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 6.0)
        img1 = self.tmp_path / "img1.png"
        img2 = self.tmp_path / "img2.png"
        img3 = self.tmp_path / "img3.png"
        Image.new("RGB", (1200, 800), color=(200, 50, 50)).save(img1)
        Image.new("RGB", (800, 1200), color=(50, 200, 50)).save(img2)
        Image.new("RGB", (1920, 1080), color=(50, 50, 200)).save(img3)

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=6.0, narration_path=narration, layout="slideshow",
            slides=[(_Panel(img1, True), 2.0), (_Panel(img2, True), 2.0), (_Panel(img3, True), 2.0)],
            output_path=out, rng=random.Random(42),
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))
        self.assertAlmostEqual(_probe_duration(out), 6.0, delta=0.3)

    def test_mixed_image_and_video_slides(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 4.0)
        img = self.tmp_path / "img.png"
        Image.new("RGB", (1200, 800), color=(200, 50, 50)).save(img)
        clip = self.tmp_path / "clip.mp4"
        _solid_clip(clip, "yellow", "640x360", duration=1.0)

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=4.0, narration_path=narration, layout="slideshow",
            slides=[(_Panel(img, True), 2.0), (_Panel(clip, False), 2.0)],
            output_path=out, rng=random.Random(7),
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))
        self.assertAlmostEqual(_probe_duration(out), 4.0, delta=0.3)

    def test_no_slides_falls_back_to_solid_background(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.0)
        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=2.0, narration_path=narration, layout="slideshow", slides=None, output_path=out,
        )
        self.assertTrue(out.exists())
        w, h, _fps = _probe_video_info(out)
        self.assertEqual((w, h), (1920, 1080))

    def test_slideshow_with_captions_and_overlays_together(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 3.0)
        captions = self.tmp_path / "captions.ass"
        _write_captions([{"text": "xin", "start": 0.0, "end": 0.3}], captions)
        img1 = self.tmp_path / "img1.png"
        img2 = self.tmp_path / "img2.png"
        Image.new("RGB", (1000, 1000), color=(90, 10, 200)).save(img1)
        Image.new("RGB", (1000, 1000), color=(10, 200, 90)).save(img2)

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(
            duration=3.0, narration_path=narration, layout="slideshow",
            slides=[(_Panel(img1, True), 1.5), (_Panel(img2, True), 1.5)],
            captions_path=captions,
            disclaimer_text="Giải trí, không phản ánh thực tế.",
            info_lines=["Truyện: X", "Tác giả: Y"],
            output_path=out, rng=random.Random(1),
        )
        self.assertTrue(out.exists())


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class MixNarrationAndMusicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_music_passes_narration_through_at_requested_duration(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 4.0)
        out = self.tmp_path / "mixed.mp3"
        _mix_narration_and_music(narration, None, 4.0, out)
        self.assertTrue(out.exists())
        self.assertAlmostEqual(_probe_duration(out), 4.0, delta=0.2)

    def test_music_shorter_than_narration_loops_to_cover_full_duration(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 6.0)
        music = self.tmp_path / "music.mp3"
        _run_ffmpeg(["-f", "lavfi", "-t", "2", "-i", "sine=frequency=110:duration=2", "-c:a", "libmp3lame", str(music)])
        out = self.tmp_path / "mixed.mp3"
        _mix_narration_and_music(narration, music, 6.0, out)
        self.assertTrue(out.exists())
        self.assertAlmostEqual(_probe_duration(out), 6.0, delta=0.2)

    def test_music_longer_than_narration_is_trimmed_to_video_duration(self):
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 2.0)
        music = self.tmp_path / "music.mp3"
        _run_ffmpeg(["-f", "lavfi", "-t", "10", "-i", "sine=frequency=220:duration=10", "-c:a", "libmp3lame", str(music)])
        out = self.tmp_path / "mixed.mp3"
        _mix_narration_and_music(narration, music, 2.0, out)
        self.assertAlmostEqual(_probe_duration(out), 2.0, delta=0.2)

    def test_mixed_audio_feeds_into_composite_like_plain_narration(self):
        # _composite doesn't know or care whether its narration_path is raw
        # narration or a pre-mixed narration+music track -- _process just
        # hands it whichever file is appropriate.
        narration = self.tmp_path / "narration.mp3"
        _silent_audio(narration, 3.0)
        music = self.tmp_path / "music.mp3"
        _run_ffmpeg(["-f", "lavfi", "-t", "3", "-i", "sine=frequency=90:duration=3", "-c:a", "libmp3lame", str(music)])
        mixed = self.tmp_path / "mixed.mp3"
        _mix_narration_and_music(narration, music, 3.0, mixed)

        out = self.tmp_path / "out.mp4"
        StorytellerService._composite(duration=3.0, narration_path=mixed, output_path=out)
        self.assertTrue(out.exists())
        self.assertAlmostEqual(_probe_duration(out), 3.0, delta=0.3)


if __name__ == "__main__":
    unittest.main()
