import inspect
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.core.exceptions import FileOperationError, ValidationError
from app.modules.motion.schemas import Easing, MotionPresetName
from app.modules.motion.service import build_motion_plan
from app.modules.motion.renderer import (
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    build_ffmpeg_command,
    build_filter_graph,
    render_motion_clip,
)

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class DefaultConfigurationTests(unittest.TestCase):
    def test_render_motion_clip_defaults_match_documented_constants(self):
        sig = inspect.signature(render_motion_clip)
        self.assertEqual(sig.parameters["fps"].default, DEFAULT_FPS)
        self.assertEqual(sig.parameters["width"].default, DEFAULT_WIDTH)
        self.assertEqual(sig.parameters["height"].default, DEFAULT_HEIGHT)


# -- Command generation (pure functions, no ffmpeg required) ------------------


class FilterGraphGenerationTests(unittest.TestCase):
    def test_static_preset_skips_zoompan_and_rotate(self):
        plan = build_motion_plan(MotionPresetName.STATIC, duration=4.0)
        graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertNotIn("zoompan", graph)
        self.assertNotIn("rotate=", graph)
        self.assertIn("scale=1080:1920", graph)
        self.assertIn("pad=1080:1920", graph)
        self.assertIn("format=yuv420p", graph)
        self.assertIn("fps=30.0", graph)

    def test_slow_push_in_uses_zoompan_with_on_and_zoom_variables(self):
        plan = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, duration=4.0)
        graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertIn("zoompan=z=", graph)
        self.assertIn("on/", graph)  # eased progress is a function of zoompan's own `on`
        self.assertIn("iw/zoom/2", graph)  # pan stays centered relative to current zoom
        self.assertIn("d=120", graph)  # 4.0s * 30fps = 120 output frames
        self.assertIn(f"s={1080}x{1920}", graph)
        self.assertNotIn("rotate=", graph)

    def test_subtle_rotate_adds_rotate_filter_using_t_not_on(self):
        plan = build_motion_plan(MotionPresetName.SUBTLE_ROTATE, duration=4.0)
        graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertIn("zoompan=z=", graph)  # subtle_rotate also has a constant zoom
        self.assertIn("rotate=", graph)
        self.assertIn("t/4.0", graph)  # rotate's own timeline variable is `t`, not `on`
        self.assertIn("PI/180", graph)  # degrees -> radians conversion for ffmpeg's rotate
        self.assertIn("fillcolor=black", graph)

    def test_zoom_and_pan_has_no_rotate_filter(self):
        plan = build_motion_plan(MotionPresetName.ZOOM_AND_PAN, duration=4.0)
        graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertIn("zoompan=z=", graph)
        self.assertNotIn("rotate=", graph)

    def test_pan_presets_have_no_rotate_filter(self):
        for preset in (
            MotionPresetName.PAN_LEFT,
            MotionPresetName.PAN_RIGHT,
            MotionPresetName.PAN_UP,
            MotionPresetName.PAN_DOWN,
        ):
            plan = build_motion_plan(preset, duration=4.0)
            graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
            self.assertNotIn("rotate=", graph, f"{preset} should not rotate")

    def test_frame_count_matches_duration_times_fps(self):
        plan = build_motion_plan(MotionPresetName.PAN_LEFT, duration=2.5)
        graph = build_filter_graph(plan, duration=2.5, fps=24.0, width=480, height=852)
        self.assertIn("d=60", graph)  # round(2.5 * 24) = 60

    def test_linear_easing_has_no_polynomial_terms(self):
        plan = build_motion_plan(MotionPresetName.PAN_LEFT, duration=4.0)
        plan = plan.model_copy(update={"easing": Easing.LINEAR})
        graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertNotIn("pow(", graph)

    def test_ease_in_out_uses_smoothstep_polynomial(self):
        plan = build_motion_plan(MotionPresetName.PAN_LEFT, duration=4.0)  # default easing is ease_in_out
        graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertIn("pow(", graph)
        self.assertIn("3*pow(", graph)  # smoothstep's leading term

    def test_deterministic_output_same_inputs_produce_identical_graph(self):
        plan = build_motion_plan(MotionPresetName.ZOOM_AND_PAN, duration=4.0)
        first = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        second = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertEqual(first, second)


class FfmpegCommandGenerationTests(unittest.TestCase):
    def test_command_structure_and_flags(self):
        plan = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, duration=4.0)
        command = build_ffmpeg_command(
            Path("in.jpg"), Path("out.mp4"), plan, duration=4.0, fps=30.0, width=1080, height=1920
        )
        self.assertEqual(command[0], "ffmpeg")
        self.assertIn("-nostdin", command)
        self.assertIn("-y", command)
        self.assertIn("-loop", command)
        self.assertIn("1", command)
        self.assertIn("-i", command)
        self.assertIn("in.jpg", command)
        self.assertIn("-t", command)
        self.assertIn("4.0", command)
        self.assertIn("-r", command)
        self.assertIn("30.0", command)
        self.assertIn("-an", command)
        self.assertIn("-pix_fmt", command)
        self.assertIn("yuv420p", command)
        self.assertIn("-color_range", command)
        self.assertIn("tv", command)
        self.assertEqual(command[-1], "out.mp4")

    def test_no_audio_related_encode_flags(self):
        plan = build_motion_plan(MotionPresetName.STATIC, duration=4.0)
        command = build_ffmpeg_command(
            Path("in.jpg"), Path("out.mp4"), plan, duration=4.0, fps=30.0, width=1080, height=1920
        )
        self.assertNotIn("-c:a", command)

    def test_deterministic_output_same_inputs_produce_identical_command(self):
        plan = build_motion_plan(MotionPresetName.PAN_UP, duration=3.0)
        first = build_ffmpeg_command(Path("a.jpg"), Path("b.mp4"), plan, 3.0, 25.0, 720, 1280)
        second = build_ffmpeg_command(Path("a.jpg"), Path("b.mp4"), plan, 3.0, 25.0, 720, 1280)
        self.assertEqual(first, second)


# -- Validation error paths (no ffmpeg execution reached, safe to always run) --


class RenderMotionClipValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.plan = build_motion_plan(MotionPresetName.STATIC, duration=1.0)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_image(self, name: str = "good.jpg") -> Path:
        path = self.tmp_path / name
        Image.new("RGB", (100, 100), color=(0, 128, 255)).save(path)
        return path

    def test_missing_input_image_raises_file_operation_error(self):
        with self.assertRaises(FileOperationError):
            render_motion_clip(self.tmp_path / "nope.jpg", self.plan, self.tmp_path / "out.mp4")

    def test_output_path_pointing_at_directory_raises_validation_error(self):
        image = self._make_image()
        out_dir = self.tmp_path / "a_directory"
        out_dir.mkdir()
        with self.assertRaises(ValidationError):
            render_motion_clip(image, self.plan, out_dir)

    def test_invalid_duration_zero_raises_validation_error(self):
        image = self._make_image()
        with self.assertRaises(ValidationError):
            render_motion_clip(image, self.plan, self.tmp_path / "out.mp4", duration=0.0)

    def test_invalid_duration_negative_raises_validation_error(self):
        image = self._make_image()
        with self.assertRaises(ValidationError):
            render_motion_clip(image, self.plan, self.tmp_path / "out.mp4", duration=-1.0)

    def test_invalid_duration_too_long_raises_validation_error(self):
        image = self._make_image()
        with self.assertRaises(ValidationError):
            render_motion_clip(image, self.plan, self.tmp_path / "out.mp4", duration=999.0)

    def test_invalid_fps_raises_validation_error(self):
        image = self._make_image()
        with self.assertRaises(ValidationError):
            render_motion_clip(image, self.plan, self.tmp_path / "out.mp4", fps=0)

    def test_odd_width_raises_validation_error(self):
        image = self._make_image()
        with self.assertRaises(ValidationError):
            render_motion_clip(image, self.plan, self.tmp_path / "out.mp4", width=1081)

    def test_missing_ffmpeg_raises_file_operation_error(self):
        image = self._make_image()
        with patch("app.modules.motion.renderer.shutil.which", return_value=None):
            with self.assertRaises(FileOperationError):
                render_motion_clip(image, self.plan, self.tmp_path / "out.mp4")

    def test_duration_override_takes_precedence_over_motion_plan_duration(self):
        # Confirmed indirectly: an out-of-range override is rejected even
        # though the underlying MotionPlan's own duration (1.0) is valid --
        # proves `duration=` really is consulted instead of being ignored.
        image = self._make_image()
        self.assertEqual(self.plan.duration, 1.0)
        with self.assertRaises(ValidationError):
            render_motion_clip(image, self.plan, self.tmp_path / "out.mp4", duration=-5.0)


# -- Real ffmpeg integration (skipped if ffmpeg/ffprobe aren't on PATH) -------


def _ffprobe_json(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,pix_fmt,codec_name",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return json.loads(result.stdout)


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class RenderMotionClipIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.image_path = self.tmp_path / "source.jpg"
        Image.new("RGB", (800, 600), color=(200, 40, 40)).save(self.image_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _render(self, preset: MotionPresetName, **overrides) -> Path:
        plan = build_motion_plan(preset, duration=overrides.pop("duration", 2.0))
        output_path = self.tmp_path / f"{preset.value}.mp4"
        return render_motion_clip(
            self.image_path,
            plan,
            output_path,
            fps=overrides.pop("fps", 12.0),
            width=overrides.pop("width", 320),
            height=overrides.pop("height", 568),
        )

    def _assert_valid_output(self, output_path: Path, expected_duration: float, fps: float, width: int, height: int):
        self.assertTrue(output_path.exists())
        probe = _ffprobe_json(output_path)
        stream = probe["streams"][0]
        self.assertEqual(stream["width"], width)
        self.assertEqual(stream["height"], height)
        self.assertEqual(stream["r_frame_rate"], f"{int(fps)}/1")
        self.assertEqual(stream["pix_fmt"], "yuv420p")
        self.assertEqual(stream["codec_name"], "h264")
        actual_duration = float(probe["format"]["duration"])
        self.assertAlmostEqual(actual_duration, expected_duration, delta=0.15)

    def test_static_preset_renders_a_valid_mp4(self):
        output_path = self._render(MotionPresetName.STATIC, duration=1.5)
        self._assert_valid_output(output_path, expected_duration=1.5, fps=12.0, width=320, height=568)

    def test_zoompan_only_preset_renders_a_valid_mp4(self):
        output_path = self._render(MotionPresetName.SLOW_PUSH_IN, duration=1.5)
        self._assert_valid_output(output_path, expected_duration=1.5, fps=12.0, width=320, height=568)

    def test_zoompan_plus_rotate_preset_renders_a_valid_mp4(self):
        output_path = self._render(MotionPresetName.SUBTLE_ROTATE, duration=1.5)
        self._assert_valid_output(output_path, expected_duration=1.5, fps=12.0, width=320, height=568)

    def test_duration_override_is_honored_in_real_output(self):
        plan = build_motion_plan(MotionPresetName.PAN_LEFT, duration=10.0)  # would be too slow to actually render
        output_path = self.tmp_path / "override.mp4"
        render_motion_clip(self.image_path, plan, output_path, duration=1.0, fps=12.0, width=320, height=568)
        probe = _ffprobe_json(output_path)
        self.assertAlmostEqual(float(probe["format"]["duration"]), 1.0, delta=0.15)

    def test_invalid_image_raises_file_operation_error(self):
        corrupt_image = self.tmp_path / "corrupt.jpg"
        corrupt_image.write_bytes(b"this is not a real image file")
        plan = build_motion_plan(MotionPresetName.STATIC, duration=1.0)
        with self.assertRaises(FileOperationError):
            render_motion_clip(corrupt_image, plan, self.tmp_path / "should_not_exist.mp4")

    def test_png_and_jpeg_sources_produce_identical_pixel_format(self):
        png_path = self.tmp_path / "source.png"
        Image.new("RGB", (800, 600), color=(10, 200, 10)).save(png_path)
        plan = build_motion_plan(MotionPresetName.ZOOM_AND_PAN, duration=1.0)

        jpg_output = self.tmp_path / "from_jpg.mp4"
        png_output = self.tmp_path / "from_png.mp4"
        render_motion_clip(self.image_path, plan, jpg_output, fps=12.0, width=320, height=568)
        render_motion_clip(png_path, plan, png_output, fps=12.0, width=320, height=568)

        jpg_pix_fmt = _ffprobe_json(jpg_output)["streams"][0]["pix_fmt"]
        png_pix_fmt = _ffprobe_json(png_output)["streams"][0]["pix_fmt"]
        self.assertEqual(jpg_pix_fmt, "yuv420p")
        self.assertEqual(png_pix_fmt, "yuv420p")


if __name__ == "__main__":
    unittest.main()
