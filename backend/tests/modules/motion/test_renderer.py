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
from app.modules.motion.schemas import Easing, MotionIntensity, MotionPresetName
from app.modules.motion.service import build_motion_plan
from app.modules.motion.renderer import (
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    build_ffmpeg_command,
    build_filter_graph,
    probe_clip,
    render_motion_clip,
    render_video_clip,
    validate_clip_output,
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
        self.assertIn("format=yuv420p", graph)
        self.assertIn("fps=30.0", graph)

    def test_static_preset_covers_the_frame_instead_of_letterboxing(self):
        # Regression test for a real bug (see
        # docs/features/34-local-motion-renderer.md): STATIC used to scale
        # with force_original_aspect_ratio=decrease + pad, which is
        # "contain" (letterboxed, black bars) not "cover". It must now
        # scale to fill (increase) and crop back to the exact target size,
        # with no pad filter (which is what produces black bars) at all.
        plan = build_motion_plan(MotionPresetName.STATIC, duration=4.0)
        graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertIn("force_original_aspect_ratio=increase", graph)
        self.assertIn("crop=1080:1920", graph)
        self.assertNotIn("pad=", graph)
        self.assertNotIn("force_original_aspect_ratio=decrease", graph)

    def test_slow_push_in_uses_zoompan_with_on_and_zoom_variables(self):
        plan = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, duration=4.0)
        graph = build_filter_graph(plan, duration=4.0, fps=30.0, width=1080, height=1920)
        self.assertIn("zoompan=z=", graph)
        self.assertIn("on/", graph)  # eased progress is a function of zoompan's own `on`
        self.assertIn("iw/zoom/2", graph)  # pan stays centered relative to current zoom
        # d is computed from the fixed zoompan reference rate (25fps),
        # never the caller's own output fps=30 -- see build_filter_graph's
        # own docstring for the real, pre-existing bug this fixes (a
        # d-from-output-fps mismatch made the pan/zoom finish early and
        # visibly freeze for the rest of the clip whenever output fps < 25).
        self.assertIn("d=100", graph)  # round(4.0 * 25) = 100
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

    def test_zoompan_frame_count_matches_duration_times_reference_fps_not_output_fps(self):
        # d must track the fixed 25fps zoompan reference rate regardless of
        # the caller's own requested output fps=24 -- see build_filter_graph's
        # own docstring for why (a real, previously-undetected freeze bug).
        plan = build_motion_plan(MotionPresetName.PAN_LEFT, duration=2.5)
        graph = build_filter_graph(plan, duration=2.5, fps=24.0, width=480, height=852)
        self.assertIn("d=62", graph)  # round(2.5 * 25) = 62, not round(2.5 * 24) = 60

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

    def test_static_preset_cover_crop_produces_no_black_corners(self):
        # Content-level regression test for the letterbox bug fixed in
        # docs/features/34-local-motion-renderer.md: width/height alone
        # can't catch it (ffmpeg reports the padded canvas size either
        # way), so this actually inspects pixels. The source (setUp) is a
        # solid, no-black color at a mismatched aspect ratio (800x600 ->
        # 320x568) -- a letterboxed corner would be pure black; a properly
        # cover-cropped one stays the source's solid color.
        output_path = self._render(MotionPresetName.STATIC, duration=1.0)
        frame_path = self.tmp_path / "frame.png"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(output_path), "-vframes", "1", str(frame_path),
            ],
            check=True,
            stdin=subprocess.DEVNULL,
        )
        frame = Image.open(frame_path).convert("RGB")
        width, height = frame.size
        for corner in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]:
            r, g, b = frame.getpixel(corner)
            self.assertFalse(r < 10 and g < 10 and b < 10, f"corner {corner} is black {(r, g, b)} -- letterbox bar")

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

    def test_zoompan_preset_does_not_distort_a_mismatched_aspect_source(self):
        # Regression test for a real bug (see
        # docs/features/34-local-motion-renderer.md): zoompan crops a
        # window whose aspect ratio equals its *input's* aspect ratio
        # regardless of zoom, so prescaling to the source's own aspect
        # ratio (instead of the output's) stretched every frame -- a
        # circle rendered as a visibly flattened ellipse. A circle drawn
        # on a source whose aspect ratio does NOT match the 9:16-ish
        # output (1600x1200, 4:3) makes that distortion directly
        # measurable: its rendered bounding box must still be ~square.
        from PIL import ImageDraw

        circle_source = self.tmp_path / "circle.png"
        img = Image.new("RGB", (1600, 1200), color=(30, 90, 160))
        ImageDraw.Draw(img).ellipse([700, 500, 900, 700], fill=(255, 255, 255))
        img.save(circle_source)

        plan = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, duration=1.0)
        output_path = self.tmp_path / "circle_push_in.mp4"
        render_motion_clip(circle_source, plan, output_path, fps=12.0, width=360, height=640)

        frame_path = self.tmp_path / "circle_frame.png"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-ss", "0", "-i", str(output_path), "-vframes", "1", str(frame_path),
            ],
            check=True,
            stdin=subprocess.DEVNULL,
        )
        frame = Image.open(frame_path).convert("RGB")
        xs, ys = [], []
        for x in range(frame.width):
            for y in range(frame.height):
                r, g, b = frame.getpixel((x, y))
                if r > 230 and g > 230 and b > 230:
                    xs.append(x)
                    ys.append(y)
        self.assertTrue(xs and ys, "white circle not found in rendered frame")
        circle_w = max(xs) - min(xs)
        circle_h = max(ys) - min(ys)
        ratio = circle_w / circle_h
        self.assertAlmostEqual(ratio, 1.0, delta=0.15, msg=f"circle bounding box {circle_w}x{circle_h} is not round (ratio={ratio:.2f}) -- frame is stretched")

    def test_pan_progresses_smoothly_across_the_whole_clip_not_just_the_start(self):
        # Regression test for a real, pre-existing bug found during Task
        # 23's own manual verification (see build_filter_graph's own
        # docstring and docs/features/49-local-motion-engine.md): computing
        # zoompan's `d` from the caller's *output* fps (rather than a fixed
        # 25fps reference) made the pan/zoom animation finish early and
        # freeze in place for the rest of the clip whenever output fps <
        # 25 -- true for almost every real fps this app uses (24, 30) and
        # every fast-rendering test fixture (10, 12fps). A left-to-right
        # gradient makes "did the crop window actually keep moving" a real,
        # measurable pixel fact rather than a guess: the sampled center
        # pixel's red channel must keep changing across effectively the
        # *entire* clip, not just an early fraction of it.
        gradient_source = self.tmp_path / "gradient.jpg"
        gradient = Image.new("RGB", (1200, 1600))
        pixels = gradient.load()
        for x in range(1200):
            shade = int(255 * x / 1200)
            for y in range(0, 1600, 8):  # sparse fill -- only speed, not correctness, matters here
                pixels[x, y] = (shade, 128, 128)
        gradient.save(gradient_source)

        plan = build_motion_plan(MotionPresetName.PAN_LEFT, duration=2.0, intensity=MotionIntensity.STRONG)
        output_path = self.tmp_path / "gradient_pan.mp4"
        render_motion_clip(gradient_source, plan, output_path, fps=10.0, width=480, height=854)

        frames_dir = self.tmp_path / "frames"
        frames_dir.mkdir()
        subprocess.run(
            ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(output_path), str(frames_dir / "f_%03d.png")],
            check=True, stdin=subprocess.DEVNULL,
        )
        frame_files = sorted(frames_dir.glob("f_*.png"))
        self.assertEqual(len(frame_files), 20)  # 2.0s * 10fps

        mid_reds = []
        for frame_file in frame_files:
            frame = Image.open(frame_file).convert("RGB")
            mid_reds.append(frame.getpixel((frame.width // 2, frame.height // 2))[0])

        # The bug's own actual signature (see build_filter_graph's own
        # docstring): the crop window reached PAN_LEFT's own endpoint
        # early, then visibly *reversed* -- jumping back toward the
        # starting position -- for the remainder of the clip, because
        # zoompan's `on` counter (driven by real decoded-input-frame
        # arrivals, not output frame count) wrapped and restarted a new
        # cycle mid-clip. A little flatness at the very start/end from
        # 8-bit quantization + ease-in-out's own genuinely-near-zero
        # velocity there is expected and NOT the bug; a same-direction,
        # monotonically non-increasing sample sequence throughout is.
        self.assertEqual(
            mid_reds, sorted(mid_reds, reverse=True),
            f"pan reversed direction mid-clip instead of moving smoothly one way -- {mid_reds}",
        )
        # And a real, non-trivial net change end-to-end -- rules out
        # "monotonic because it barely moved at all."
        self.assertGreater(mid_reds[0] - mid_reds[-1], 5, f"pan moved too little overall -- {mid_reds}")

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


class FocalPointStaticCropTests(unittest.TestCase):
    def test_center_focal_point_produces_the_original_plain_crop_expression(self):
        # Backward-compat guard (Task 23 -- see docs/features/49-local-
        # motion-engine.md section 32): the default 0.5/0.5 focal point
        # must produce the exact original filter string, byte for byte.
        plan = build_motion_plan(MotionPresetName.STATIC, duration=2.0)
        graph = build_filter_graph(plan, duration=2.0, fps=30.0, width=1080, height=1920)
        self.assertIn("crop=1080:1920", graph)
        self.assertNotIn("crop=1080:1920:x=", graph)

    def test_off_center_focal_point_adds_an_explicit_crop_offset(self):
        plan = build_motion_plan(MotionPresetName.STATIC, duration=2.0)
        graph = build_filter_graph(plan, duration=2.0, fps=30.0, width=1080, height=1920, focal_x=0.8, focal_y=0.2)
        self.assertIn("crop=1080:1920:x=", graph)
        self.assertIn("0.8", graph)
        self.assertIn("0.2", graph)


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class RenderVideoClipIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.source_path = self.tmp_path / "source.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x480:rate=30:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.source_path),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_trims_a_longer_source_to_the_requested_duration(self):
        output_path = self.tmp_path / "trimmed.mp4"
        render_video_clip(self.source_path, output_path, duration=1.0, width=480, height=854)
        probe = probe_clip(output_path)
        self.assertAlmostEqual(probe.duration_sec, 1.0, delta=0.15)
        self.assertEqual((probe.width, probe.height), (480, 854))

    def test_freeze_policy_extends_a_shorter_source_by_holding_the_last_frame(self):
        output_path = self.tmp_path / "freeze.mp4"
        render_video_clip(self.source_path, output_path, duration=4.0, width=480, height=854, short_source_policy="FREEZE")
        probe = probe_clip(output_path)
        self.assertAlmostEqual(probe.duration_sec, 4.0, delta=0.2)

    def test_loop_policy_extends_a_shorter_source_by_repeating_it(self):
        output_path = self.tmp_path / "loop.mp4"
        render_video_clip(self.source_path, output_path, duration=4.0, width=480, height=854, short_source_policy="LOOP")
        probe = probe_clip(output_path)
        self.assertAlmostEqual(probe.duration_sec, 4.0, delta=0.2)

    def test_reject_policy_raises_instead_of_rendering(self):
        output_path = self.tmp_path / "reject.mp4"
        with self.assertRaises(ValidationError):
            render_video_clip(self.source_path, output_path, duration=4.0, width=480, height=854, short_source_policy="REJECT")
        self.assertFalse(output_path.exists())

    def test_output_has_no_audio_track(self):
        # Section 43: Beat clips are video-only -- narration/BGM composition
        # happens later, never muxed in per-clip here.
        output_path = self.tmp_path / "silent.mp4"
        render_video_clip(self.source_path, output_path, duration=1.0, width=480, height=854)
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", str(output_path)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        self.assertEqual(result.stdout.strip(), "")

    def test_missing_source_raises_file_operation_error(self):
        with self.assertRaises(FileOperationError):
            render_video_clip(self.tmp_path / "nope.mp4", self.tmp_path / "out.mp4", duration=1.0, width=480, height=854)

    def test_unknown_policy_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            render_video_clip(self.source_path, self.tmp_path / "out.mp4", duration=1.0, width=480, height=854, short_source_policy="EXPLODE")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class ClipOutputValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.image_path = self.tmp_path / "source.jpg"
        Image.new("RGB", (800, 600), color=(200, 40, 40)).save(self.image_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_probe_and_validate_a_real_rendered_clip(self):
        plan = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, duration=1.5)
        output_path = self.tmp_path / "clip.mp4"
        render_motion_clip(self.image_path, plan, output_path, fps=24.0, width=480, height=854)
        probe = probe_clip(output_path)
        validate_clip_output(probe, expected_duration=1.5, expected_width=480, expected_height=854, expected_fps=24.0)

    def test_wrong_expected_resolution_raises(self):
        plan = build_motion_plan(MotionPresetName.STATIC, duration=1.0)
        output_path = self.tmp_path / "clip.mp4"
        render_motion_clip(self.image_path, plan, output_path, fps=24.0, width=480, height=854)
        probe = probe_clip(output_path)
        with self.assertRaises(FileOperationError):
            validate_clip_output(probe, expected_duration=1.0, expected_width=1080, expected_height=1920, expected_fps=24.0)

    def test_wrong_expected_duration_raises(self):
        plan = build_motion_plan(MotionPresetName.STATIC, duration=1.0)
        output_path = self.tmp_path / "clip.mp4"
        render_motion_clip(self.image_path, plan, output_path, fps=24.0, width=480, height=854)
        probe = probe_clip(output_path)
        with self.assertRaises(FileOperationError):
            validate_clip_output(probe, expected_duration=5.0, expected_width=480, expected_height=854, expected_fps=24.0)

    def test_duration_within_frame_tolerance_passes(self):
        plan = build_motion_plan(MotionPresetName.STATIC, duration=1.0)
        output_path = self.tmp_path / "clip.mp4"
        render_motion_clip(self.image_path, plan, output_path, fps=24.0, width=480, height=854)
        probe = probe_clip(output_path)
        # A tiny, sub-frame nudge must still pass (section 40's own
        # "do not require exact floating-point equality").
        validate_clip_output(probe, expected_duration=probe.duration_sec + 0.01, expected_width=480, expected_height=854, expected_fps=24.0)

    def test_probe_unreadable_file_raises_file_operation_error(self):
        bogus = self.tmp_path / "not_a_video.mp4"
        bogus.write_bytes(b"nope")
        with self.assertRaises(FileOperationError):
            probe_clip(bogus)


if __name__ == "__main__":
    unittest.main()
