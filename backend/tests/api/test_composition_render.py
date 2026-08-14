import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import selectinload, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.composition_render import (
    _DEFAULT_TRANSITION_DURATION,
    _build_sfx_cues,
    _compute_scene_start_times,
    _derive_transition_duration,
    _is_image_path,
    _probe_audio_duration,
    _resolve_narration,
    _scene_motion_to_motion_plan,
    render_beats_for_job,
    render_composition,
)
from app.core.exceptions import FileOperationError, ValidationError
from app.db.base import Base
from app.modules.composition.schemas import (
    CaptionPreset,
    CompositionPlan,
    Easing,
    OutputFormat,
    PositionRange,
    RotationRange,
    ScaleRange,
    Scene,
    SceneAudio,
    SceneMotion,
    SceneTransition,
    TransitionType,
)
from app.modules.motion.schemas import Easing as MotionEasing
from app.modules.motion.schemas import MotionPresetName
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob
from app.modules.video_composer.service import VideoComposerService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


# -- test fixtures/helpers ----------------------------------------------------


def _make_solid_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (640, 640)) -> Path:
    Image.new("RGB", size, color=color).save(path)
    return path


def _make_color_clip(path: Path, duration: float, color: str, width: int, height: int, fps: float) -> Path:
    """A tiny real video clip synthesized locally via ffmpeg's lavfi color
    source -- used to prove the *existing*, upload-based composer flow
    (which needs a real video clip, not an image) still works, without
    depending on any external asset.
    """
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        stdin=subprocess.DEVNULL,
    )
    return path


def _ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return float(result.stdout.strip())


def _default_motion() -> SceneMotion:
    return SceneMotion(
        preset_name="zoom_and_pan",
        scale=ScaleRange(start=1.0, end=1.1),
        position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.55, y_end=0.45),
    )


def _make_scene(
    scene_id: str,
    order: int,
    duration: float,
    asset_id: int,
    width: int = 320,
    height: int = 568,
    fps: float = 12.0,
    transition_duration: float = 0.3,
    narration_asset_id: int | None = None,
) -> Scene:
    return Scene(
        id=scene_id,
        order=order,
        duration=duration,
        source_asset_id=asset_id,
        motion=_default_motion(),
        audio=SceneAudio(narration_asset_id=narration_asset_id),
        transition=SceneTransition(type=TransitionType.CROSSFADE, duration=transition_duration),
        output_format=OutputFormat(width=width, height=height, fps=fps),
    )


def _fake_run_narration(script_text: str, voice: str, output_path: Path) -> list[dict]:
    """Stands in for VideoComposerService._run_narration, which normally
    calls Microsoft's edge-tts cloud service. Generates a short *local*
    silent audio track via ffmpeg instead (no network, no external API --
    "do not require external APIs"), and returns plausible word timestamps
    so the rest of the real, unmodified pipeline (subtitling, audio mixing,
    finalize) still runs against real, well-formed data.
    """
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "1.0",
            "-c:a",
            "libmp3lame",
            str(output_path),
        ],
        check=True,
        stdin=subprocess.DEVNULL,
    )
    return [{"start": 0.0, "end": 0.5, "text": "Test"}, {"start": 0.5, "end": 1.0, "text": "narration"}]


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class _VideoComposerIntegrationTestCase(unittest.TestCase):
    """Each test gets its own in-memory SQLite DB (only video_compose_job/
    video_compose_clip tables -- this is video_composer's own schema, not a
    reason to import anything else) with app.modules.video_composer.service's
    SessionLocal patched to it, so tests never touch the real dev database.
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

        self.service = VideoComposerService(library_dir=self.tmp_path, beat_renderer=render_beats_for_job)

    def tearDown(self):
        self.session_patcher.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _get_job(self, job_id: int) -> VideoComposeJob:
        db = self.TestSessionLocal()
        try:
            return (
                db.query(VideoComposeJob)
                .options(selectinload(VideoComposeJob.clips))
                .filter(VideoComposeJob.id == job_id)
                .first()
            )
        finally:
            db.close()

    def _run_job_with_mocked_narration(self, job_id: int) -> None:
        with patch.object(self.service, "_run_narration", side_effect=_fake_run_narration):
            self.service._run_job(job_id)


# -- 1. existing composer still works (regression) ----------------------------


class ExistingComposerRegressionTests(_VideoComposerIntegrationTestCase):
    def test_upload_based_job_still_completes_successfully(self):
        clip1 = _make_color_clip(self.tmp_path / "clip1.mp4", 1.0, "red", 320, 568, 12.0)
        clip2 = _make_color_clip(self.tmp_path / "clip2.mp4", 1.0, "blue", 320, 568, 12.0)

        job_id = self.service.create_job(
            title="Old Upload Flow",
            script_text="Hello world",
            voice="en-US-GuyNeural",
            music_volume=0.15,
            transition_duration=0.3,
            burn_subtitles=True,
            requested_output_dir=None,
        )
        with open(clip1, "rb") as f1, open(clip2, "rb") as f2:
            self.service.save_input_clips(job_id, [("clip1.mp4", f1), ("clip2.mp4", f2)])

        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        self.assertIsNotNone(job.output_path)
        self.assertTrue(Path(job.output_path).exists())


class FullLocalEndToEndPipelineTests(_VideoComposerIntegrationTestCase):
    """Task 10's own full-pipeline scenario (docs/features/37-e2e-pipeline-hardening.md):
    a tiny, fully local project -- 3 beats, 2s each, local images, local
    narration, local music -- run through the real render_composition()
    adapter (preflight -> motion rendering -> the real, unmocked
    VideoComposerService._run_job) with only the DB session mocked (see
    _VideoComposerIntegrationTestCase), exactly this task's own "exercise
    real service boundaries, mock only external dependencies" instruction.
    Nothing here calls edge_tts (local narration mode never does), so no
    mock is even needed for narration.

    Captions are deliberately NOT enabled in this scenario:
    render_composition forces `burn_subtitles=False` whenever local
    narration is used, since a pre-recorded local clip carries no
    word-boundary transcript to caption from (a pre-existing, documented
    constraint from docs/features/36-audio-pipeline.md, not something this
    task changes -- building local speech-to-text to caption arbitrary
    narration audio would be a new AI feature, explicitly out of this
    "integration and hardening only" task's scope). Captions-with-TTS
    narration is already covered by FinalMuxingWithAudioAndCaptionsTests
    above; that combination is not free ($0), which is exactly why it's
    a separate scenario from this one.
    """

    def test_three_local_beats_with_local_narration_and_music_render_free_and_valid(self):
        image1 = _make_solid_image(self.tmp_path / "beat1.jpg", color=(200, 40, 40))
        image2 = _make_solid_image(self.tmp_path / "beat2.jpg", color=(40, 200, 40))
        image3 = _make_solid_image(self.tmp_path / "beat3.jpg", color=(40, 40, 200))
        narration = self.tmp_path / "narration.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5",
                "-c:a", "libmp3lame", str(narration),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        music = self.tmp_path / "music.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=3",
                "-c:a", "libmp3lame", str(music),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )

        plan = CompositionPlan(
            music_path=str(music),
            music_volume=0.2,
            scenes=[
                _make_scene("beat_01", 1, 2.0, asset_id=101, narration_asset_id=201),
                _make_scene("beat_02", 2, 2.0, asset_id=102, narration_asset_id=202),
                _make_scene("beat_03", 3, 2.0, asset_id=103, narration_asset_id=203),
            ],
        )
        asset_paths = {101: str(image1), 102: str(image2), 103: str(image3)}
        narration_asset_paths = {201: str(narration), 202: str(narration), 203: str(narration)}

        job_id = render_composition(
            plan, asset_paths, self.service, title="Full local pipeline",
            narration_asset_paths=narration_asset_paths,
        )

        job_before_run = self._get_job(job_id)
        self.assertEqual(job_before_run.status, "queued")
        self.assertEqual(job_before_run.narration_mode, "local")
        self.assertFalse(job_before_run.burn_subtitles)
        self.assertEqual(job_before_run.render_profile, "SOCIAL_VERTICAL")
        self.assertIsInstance(job_before_run.preflight_seconds, float)
        # RENDER_BEATS now runs on the worker (Task 11), not synchronously
        # inside render_composition -- not timed yet at this point.
        self.assertIsNone(job_before_run.beat_render_seconds)

        # Real, unmocked pipeline -- no edge_tts patch anywhere in this
        # test. If narration_mode ever silently fell back to "tts", this
        # would either hang on a real network call or fail outright.
        self.service._run_job(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        self.assertIsInstance(job.beat_render_seconds, float)
        output_path = Path(job.output_path)
        self.assertTrue(output_path.exists())

        probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
                "-show_entries", "format=duration", "-of", "json", str(output_path),
            ],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        data = json.loads(probe.stdout)
        video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
        audio_stream = next(s for s in data["streams"] if s["codec_type"] == "audio")
        self.assertEqual(video_stream["codec_name"], "h264")
        self.assertEqual(audio_stream["codec_name"], "aac")
        # 3x 2s beats; _make_scene defaults each scene's transition to 0.3s,
        # and _derive_transition_duration averages the 2 non-first scenes'
        # 0.3s transitions -> 0.3s used for both crossfades:
        # 6.0 - 2*0.3 = 5.4s.
        self.assertAlmostEqual(float(data["format"]["duration"]), 5.4, delta=0.3)

        report_path = self.tmp_path / ".render" / f"job_{job_id}" / "report.json"
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["beats"], 3)
        self.assertFalse(report["captions"])
        self.assertEqual(report["external_api_calls"], 0)
        self.assertEqual(report["external_api_cost_estimate"], 0)
        self.assertEqual(report["video"]["video_codec"], "h264")
        self.assertEqual(report["video"]["audio_codec"], "aac")


# -- 2/3/4/5. CompositionPlan works, scenes concatenate, duration, output exists --


class CompositionPlanIntegrationTests(_VideoComposerIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.image1 = _make_solid_image(self.tmp_path / "img1.jpg", color=(200, 40, 40))
        self.image2 = _make_solid_image(self.tmp_path / "img2.jpg", color=(40, 200, 40))

    def test_composition_plan_scenes_render_and_are_saved_in_order(self):
        plan = CompositionPlan(
            narration_script="A short composed story.",
            voice="en-US-GuyNeural",
            scenes=[
                _make_scene("scene_01", 1, 1.0, asset_id=101),
                _make_scene("scene_02", 2, 1.0, asset_id=102),
            ],
        )
        asset_paths = {101: str(self.image1), 102: str(self.image2)}

        job_id = render_composition(plan, asset_paths, self.service, title="Composed")

        job = self._get_job(job_id)
        # RENDER_BEATS now runs on the worker (Task 11), not synchronously
        # inside render_composition -- immediately after it returns, the
        # job is queued and has no clips yet.
        self.assertEqual(job.status, "queued")
        self.assertEqual(len(job.clips), 0)

        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        ordered_clips = sorted(job.clips, key=lambda c: c.position)
        self.assertEqual(len(ordered_clips), 2)
        self.assertIn("scene_01", ordered_clips[0].file_path)
        self.assertIn("scene_02", ordered_clips[1].file_path)
        for clip in ordered_clips:
            self.assertTrue(Path(clip.file_path).exists(), f"{clip.file_path} should be rendered on disk")

    def test_composition_plan_completes_with_correct_duration_and_output_file(self):
        transition_duration = 0.3
        plan = CompositionPlan(
            narration_script="A short composed story.",
            voice="en-US-GuyNeural",
            scenes=[
                _make_scene("scene_01", 1, 1.0, asset_id=101, transition_duration=transition_duration),
                _make_scene("scene_02", 2, 1.0, asset_id=102, transition_duration=transition_duration),
            ],
        )
        asset_paths = {101: str(self.image1), 102: str(self.image2)}

        job_id = render_composition(plan, asset_paths, self.service, title="Composed")
        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        self.assertIsNotNone(job.output_path)

        output_path = Path(job.output_path)
        self.assertTrue(output_path.exists())

        # Same overlap formula app.modules.video_composer.service's own
        # _merge_clips_with_transitions uses for 2 clips: total duration is
        # the sum of clip durations minus one transition's worth of overlap.
        expected_duration = 1.0 + (1.0 - transition_duration)
        self.assertAlmostEqual(_ffprobe_duration(output_path), expected_duration, delta=0.25)

    def test_three_scenes_concatenate_and_extend_total_duration(self):
        image3 = _make_solid_image(self.tmp_path / "img3.jpg", color=(40, 40, 200))
        plan = CompositionPlan(
            scenes=[
                _make_scene("scene_01", 1, 1.0, asset_id=101, transition_duration=0.2),
                _make_scene("scene_02", 2, 1.0, asset_id=102, transition_duration=0.2),
                _make_scene("scene_03", 3, 1.0, asset_id=103, transition_duration=0.2),
            ]
        )
        asset_paths = {101: str(self.image1), 102: str(self.image2), 103: str(image3)}

        job_id = render_composition(plan, asset_paths, self.service)
        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        ordered_clips = sorted(job.clips, key=lambda c: c.position)
        self.assertEqual(len(ordered_clips), 3)

        # 3 one-second clips, two 0.2s overlaps: 1.0 + (1.0-0.2) + (1.0-0.2) = 2.6s
        self.assertAlmostEqual(_ffprobe_duration(Path(job.output_path)), 2.6, delta=0.3)

    def test_three_beats_two_seconds_each_concatenate_in_correct_visual_order(self):
        # Task 35's literal example ("3 test beats, 2 seconds each") plus
        # its own "do not test only filenames -- use deterministic
        # fixtures" instruction: this samples actual pixel colors from the
        # *final merged* output at each beat's mid-point, not just clip
        # file paths/positions (already covered by the ordering test
        # above), proving beat_01/02/03 truly concatenate in that visual
        # order, not just that their file paths were saved in that order.
        red = self.image1  # (200, 40, 40), from setUp
        green = self.image2  # (40, 200, 40), from setUp
        blue = _make_solid_image(self.tmp_path / "img3_blue.jpg", color=(40, 40, 200))
        transition_duration = 0.1
        plan = CompositionPlan(
            scenes=[
                _make_scene("scene_01", 1, 2.0, asset_id=101, transition_duration=transition_duration),
                _make_scene("scene_02", 2, 2.0, asset_id=102, transition_duration=transition_duration),
                _make_scene("scene_03", 3, 2.0, asset_id=103, transition_duration=transition_duration),
            ]
        )
        asset_paths = {101: str(red), 102: str(green), 103: str(blue)}

        job_id = render_composition(plan, asset_paths, self.service)
        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        output_path = Path(job.output_path)

        # 3 two-second clips, two 0.1s overlaps: 2.0 + (2.0-0.1)*2 = 5.8s
        actual_duration = _ffprobe_duration(output_path)
        self.assertAlmostEqual(actual_duration, 5.8, delta=0.3)

        probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name,pix_fmt",
                "-of", "json", str(output_path),
            ],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        stream = json.loads(probe.stdout)["streams"][0]
        self.assertEqual(stream["width"], 320)
        self.assertEqual(stream["height"], 568)
        self.assertEqual(stream["codec_name"], "h264")
        self.assertEqual(stream["pix_fmt"], "yuv420p")

        def _sample_color(timestamp: float) -> tuple[int, int, int]:
            frame_path = self.tmp_path / f"frame_{timestamp}.png"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-ss", str(timestamp), "-i", str(output_path), "-vframes", "1", str(frame_path),
                ],
                check=True, stdin=subprocess.DEVNULL,
            )
            return Image.open(frame_path).convert("RGB").getpixel((5, 5))

        def _assert_close(actual: tuple[int, int, int], expected: tuple[int, int, int], label: str):
            for a, e in zip(actual, expected):
                self.assertLess(abs(a - e), 40, f"{label}: sampled {actual}, expected ~{expected}")

        _assert_close(_sample_color(1.0), (200, 40, 40), "beat 1 (red) mid-point")
        _assert_close(_sample_color(2.9), (40, 200, 40), "beat 2 (green) mid-point")
        _assert_close(_sample_color(4.8), (40, 40, 200), "beat 3 (blue) mid-point")

    def test_video_asset_scene_is_used_directly_without_motion_rendering(self):
        # A Scene whose asset is already a video clip (e.g. sourced from
        # Scene Cutter output) should be used as-is, not run through the
        # motion renderer (which expects a still image).
        video_clip = _make_color_clip(self.tmp_path / "already_a_clip.mp4", 1.0, "green", 320, 568, 12.0)
        plan = CompositionPlan(
            scenes=[
                _make_scene("scene_01", 1, 1.0, asset_id=101),
                _make_scene("scene_02", 2, 1.0, asset_id=102),
            ]
        )
        asset_paths = {101: str(self.image1), 102: str(video_clip)}

        job_id = render_composition(plan, asset_paths, self.service)
        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        ordered_clips = sorted(job.clips, key=lambda c: c.position)
        # scene_02's clip path is the original video file itself, not a
        # newly rendered one under the job's scenes/ directory.
        self.assertEqual(ordered_clips[1].file_path, str(video_clip))

    def test_missing_asset_path_mapping_raises_validation_error(self):
        plan = CompositionPlan(scenes=[_make_scene("scene_01", 1, 1.0, asset_id=101)])
        with self.assertRaises(ValidationError):
            render_composition(plan, asset_paths={}, service=self.service)


# -- final muxing: video + narration + music + SFX + captions = final.mp4 -----


class FinalMuxingWithAudioAndCaptionsTests(_VideoComposerIntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.image1 = _make_solid_image(self.tmp_path / "img1.jpg", color=(200, 40, 40))
        self.image2 = _make_solid_image(self.tmp_path / "img2.jpg", color=(40, 200, 40))
        self.music = self.tmp_path / "music.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=5",
                "-c:a", "libmp3lame", str(self.music),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        self.sfx = self.tmp_path / "sfx.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=880:duration=0.3",
                "-c:a", "libmp3lame", str(self.sfx),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )

    def test_composition_with_narration_music_sfx_and_captions_produces_valid_final_mp4(self):
        plan = CompositionPlan(
            narration_script="A short composed story with music and captions.",
            voice="en-US-GuyNeural",
            narration_volume=0.9,
            music_path=str(self.music),
            music_volume=0.2,
            music_ducking_ratio=10.0,
            fade_in_sec=0.2,
            fade_out_sec=0.2,
            caption_preset=CaptionPreset.CINEMATIC,
            scenes=[
                Scene(
                    id="scene_01",
                    order=1,
                    duration=1.0,
                    source_asset_id=101,
                    motion=_default_motion(),
                    audio=SceneAudio(sfx=str(self.sfx), sfx_volume=0.7),
                    transition=SceneTransition(type=TransitionType.CROSSFADE, duration=0.3),
                    output_format=OutputFormat(width=320, height=568, fps=12.0),
                ),
                _make_scene("scene_02", 2, 1.0, asset_id=102),
            ],
        )
        asset_paths = {101: str(self.image1), 102: str(self.image2)}

        job_id = render_composition(plan, asset_paths, self.service, title="Full Mix")

        # sfx cue was actually threaded through to the job as a persisted
        # setting -- confirms the adapter -> video_composer wiring, not just
        # that render_composition ran without raising.
        job_before_run = self._get_job(job_id)
        self.assertEqual(job_before_run.caption_preset, "cinematic")
        self.assertAlmostEqual(job_before_run.narration_volume, 0.9)
        self.assertAlmostEqual(job_before_run.music_ducking_ratio, 10.0)
        self.assertIsNotNone(job_before_run.sfx_cues)
        self.assertEqual(len(job_before_run.sfx_cues), 1)
        self.assertEqual(job_before_run.sfx_cues[0]["path"], str(self.sfx))

        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        self.assertIsNotNone(job.output_path)
        output_path = Path(job.output_path)
        self.assertTrue(output_path.exists())

        # final muxing: the finished file must carry both a video stream
        # (with captions burned in, unverifiable pixel-by-pixel here, but
        # subtitle_srt_path being set proves captions were generated and
        # fed to the same finalize step that burns them) and an audio
        # stream (narration + ducked music + SFX, all mixed together).
        self.assertIsNotNone(job.subtitle_srt_path)
        self.assertTrue(Path(job.subtitle_srt_path).exists())

        probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                "-of", "csv=p=0", str(output_path),
            ],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        stream_types = set(probe.stdout.split())
        self.assertIn("video", stream_types)
        self.assertIn("audio", stream_types)


# -- 6. ffmpeg failures are surfaced correctly ---------------------------------


class FfmpegFailureSurfacingTests(_VideoComposerIntegrationTestCase):
    def test_corrupt_image_fails_the_job_during_render_beats(self):
        # A corrupt image passes preflight (the file exists and is
        # readable -- preflight doesn't decode it) but fails once the
        # worker actually tries to render motion from it. Task 11 moved
        # RENDER_BEATS off the request thread (see
        # docs/features/38-render-job-hardening.md), so this is no longer
        # a synchronous raise out of render_composition -- it's an async
        # job failure, exactly like every other render failure.
        corrupt_image = self.tmp_path / "corrupt.jpg"
        corrupt_image.write_bytes(b"this is not a real image")
        plan = CompositionPlan(scenes=[_make_scene("scene_01", 1, 1.0, asset_id=101)])

        job_id = render_composition(plan, {101: str(corrupt_image)}, self.service)
        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "failed")
        self.assertTrue(job.error_message)

    def test_merge_stage_ffmpeg_failure_marks_job_failed_with_error_message(self):
        # A file that *looks* like a video (by extension, so it skips
        # motion rendering and is passed straight to the merge step) but
        # isn't real media -- the existing, unmodified _run_job/
        # _probe_video_info must still catch this and fail the job
        # cleanly, exactly as it already does for the upload-based flow.
        corrupt_clip = self.tmp_path / "corrupt.mp4"
        corrupt_clip.write_bytes(b"not a real video file")
        plan = CompositionPlan(scenes=[_make_scene("scene_01", 1, 1.0, asset_id=101)])

        job_id = render_composition(plan, {101: str(corrupt_clip)}, self.service)
        self._run_job_with_mocked_narration(job_id)

        job = self._get_job(job_id)
        self.assertEqual(job.status, "failed")
        self.assertTrue(job.error_message)


# -- pure unit tests for the adapter's own helpers (no ffmpeg/DB required) ----


class ResolveNarrationTests(unittest.TestCase):
    """_resolve_narration is pure decision logic + validation (no ffmpeg
    execution of its own beyond ffprobe-ing real audio files for the
    duration checks) -- see docs/features/36-audio-pipeline.md.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_tone(self, name: str, duration: float) -> Path:
        path = self.tmp_path / name
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
                "-c:a", "libmp3lame", str(path),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        return path

    def test_no_scene_has_narration_asset_returns_tts_mode_backward_compatibly(self):
        plan = CompositionPlan(
            narration_script="A story.",
            scenes=[_make_scene("scene_01", 1, 4.0, asset_id=101), _make_scene("scene_02", 2, 4.0, asset_id=102)],
        )
        mode, specs = _resolve_narration(plan, narration_asset_paths=None, transition_duration=0.3)
        self.assertEqual(mode, "tts")
        self.assertIsNone(specs)

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_local_mode_selected_when_any_scene_has_narration_asset(self):
        tone = self._make_tone("n.mp3", 1.0)
        plan = CompositionPlan(
            scenes=[_make_scene("scene_01", 1, 4.0, asset_id=101, narration_asset_id=501)]
        )
        mode, specs = _resolve_narration(plan, narration_asset_paths={501: str(tone)}, transition_duration=0.3)
        self.assertEqual(mode, "local")
        # The only scene -- there's no predecessor to crossfade-overlap
        # with, so its timeline share is its full, un-adjusted duration.
        self.assertEqual(specs, [{"duration": 4.0, "path": str(tone)}])

    def test_narration_asset_id_set_but_no_path_mapping_raises_validation_error(self):
        plan = CompositionPlan(
            scenes=[_make_scene("scene_01", 1, 4.0, asset_id=101, narration_asset_id=501)]
        )
        with self.assertRaises(ValidationError) as ctx:
            _resolve_narration(plan, narration_asset_paths={}, transition_duration=0.3)
        self.assertIn("Beat 1", str(ctx.exception))

    def test_narration_file_missing_on_disk_raises_file_operation_error(self):
        plan = CompositionPlan(
            scenes=[_make_scene("scene_01", 1, 4.0, asset_id=101, narration_asset_id=501)]
        )
        missing = self.tmp_path / "gone.mp3"
        with self.assertRaises(FileOperationError):
            _resolve_narration(plan, narration_asset_paths={501: str(missing)}, transition_duration=0.3)

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_narration_shorter_than_beat_duration_is_accepted(self):
        tone = self._make_tone("short.mp3", 2.0)
        plan = CompositionPlan(scenes=[_make_scene("scene_01", 1, 4.0, asset_id=101, narration_asset_id=501)])
        mode, specs = _resolve_narration(plan, narration_asset_paths={501: str(tone)}, transition_duration=0.3)
        self.assertEqual(mode, "local")
        self.assertEqual(specs[0]["duration"], 4.0)  # beat duration, not narration's own

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_narration_longer_than_beat_duration_rejected_with_clear_message(self):
        tone = self._make_tone("long.mp3", 5.8)
        plan = CompositionPlan(
            scenes=[
                _make_scene("scene_01", 1, 4.0, asset_id=101),
                _make_scene("scene_02", 2, 4.0, asset_id=102),
                _make_scene("scene_03", 3, 4.0, asset_id=103, narration_asset_id=501),
            ]
        )
        with self.assertRaises(ValidationError) as ctx:
            _resolve_narration(plan, narration_asset_paths={501: str(tone)}, transition_duration=0.3)
        message = str(ctx.exception)
        self.assertIn("Beat 3", message)
        # Validated against the beat's own, raw, user-facing duration -- not
        # the crossfade-shortened timeline share (see _resolve_narration's
        # own docstring for why those are deliberately different numbers).
        self.assertIn("4.0s", message)

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_beat_without_narration_asset_gets_none_path_preserving_the_gap(self):
        tone = self._make_tone("n.mp3", 1.0)
        plan = CompositionPlan(
            scenes=[
                _make_scene("scene_01", 1, 4.0, asset_id=101, narration_asset_id=501),
                _make_scene("scene_02", 2, 3.0, asset_id=102, narration_asset_id=None),
                _make_scene("scene_03", 3, 5.0, asset_id=103, narration_asset_id=501),
            ]
        )
        mode, specs = _resolve_narration(plan, narration_asset_paths={501: str(tone)}, transition_duration=0.3)
        self.assertEqual(mode, "local")
        self.assertEqual([s["path"] for s in specs], [str(tone), None, str(tone)])
        # scene 1: first scene, no overlap to lose. scenes 2/3: each loses
        # safe_transition=min(0.3, shortest/2)=0.3s to the crossfade with
        # its predecessor -- 3.0-0.3=2.7, 5.0-0.3=4.7.
        self.assertEqual([s["duration"] for s in specs], [4.0, 2.7, 4.7])

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_specs_total_duration_matches_the_actual_merged_video_duration(self):
        # The whole point of the crossfade adjustment: concatenating the
        # spec durations must equal what _merge_clips_with_transitions
        # actually produces (sum of durations minus one safe_transition per
        # transition), not the naive sum of raw beat durations -- otherwise
        # local narration drifts out of sync with the video it's paired
        # with, worse the more beats/transitions there are.
        tone = self._make_tone("n.mp3", 1.0)
        plan = CompositionPlan(
            scenes=[
                _make_scene("scene_01", 1, 4.0, asset_id=101, narration_asset_id=501),
                _make_scene("scene_02", 2, 5.0, asset_id=102),
                _make_scene("scene_03", 3, 4.0, asset_id=103),
                _make_scene("scene_04", 4, 6.0, asset_id=104),
                _make_scene("scene_05", 5, 4.0, asset_id=105, narration_asset_id=501),
            ]
        )
        _, specs = _resolve_narration(plan, narration_asset_paths={501: str(tone)}, transition_duration=0.4)
        # 4 + 5 + 4 + 6 + 4 = 23 raw; 4 transitions * 0.4s = 1.6s overlap;
        # 23 - 1.6 = 21.4s -- the exact figure this task's own manual
        # verification (docs/features/36-audio-pipeline.md) measured for
        # the real merged video.
        self.assertAlmostEqual(sum(s["duration"] for s in specs), 21.4, places=5)


class AudioProbeTests(unittest.TestCase):
    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_probe_audio_duration_returns_real_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tone.mp3"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2.5",
                    "-c:a", "libmp3lame", str(path),
                ],
                check=True, stdin=subprocess.DEVNULL,
            )
            self.assertAlmostEqual(_probe_audio_duration(path), 2.5, delta=0.1)


class AdapterHelperUnitTests(unittest.TestCase):
    def test_is_image_path_recognizes_common_image_extensions(self):
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".JPG", ".PNG"):
            self.assertTrue(_is_image_path(Path(f"file{ext}")), ext)

    def test_is_image_path_rejects_video_extensions(self):
        for ext in (".mp4", ".mov", ".mkv"):
            self.assertFalse(_is_image_path(Path(f"file{ext}")), ext)

    def test_derive_transition_duration_defaults_when_no_real_transitions(self):
        scenes = [_make_scene("scene_01", 1, 1.0, asset_id=101)]
        self.assertEqual(_derive_transition_duration(scenes), _DEFAULT_TRANSITION_DURATION)

    def test_derive_transition_duration_averages_non_first_scene_transitions(self):
        scenes = [
            _make_scene("scene_01", 1, 1.0, asset_id=101, transition_duration=0.9),  # order 1, excluded
            _make_scene("scene_02", 2, 1.0, asset_id=102, transition_duration=0.2),
            _make_scene("scene_03", 3, 1.0, asset_id=103, transition_duration=0.6),
        ]
        self.assertAlmostEqual(_derive_transition_duration(scenes), 0.4)  # avg(0.2, 0.6)

    def test_scene_motion_to_motion_plan_converts_fields_correctly(self):
        scene_motion = SceneMotion(
            preset_name="slow_push_in",
            scale=ScaleRange(start=1.0, end=1.08),
            position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.52, y_end=0.48),
            rotation=RotationRange(start=0.0, end=0.0),
            easing=Easing.EASE_IN_OUT,
        )
        motion_plan = _scene_motion_to_motion_plan(scene_motion, duration=3.0)
        self.assertEqual(motion_plan.preset, MotionPresetName.SLOW_PUSH_IN)
        self.assertEqual(motion_plan.duration, 3.0)
        self.assertEqual(motion_plan.scale.start, 1.0)
        self.assertEqual(motion_plan.scale.end, 1.08)
        self.assertEqual(motion_plan.position.x_end, 0.52)
        self.assertEqual(motion_plan.easing, MotionEasing.EASE_IN_OUT)

    def test_scene_motion_to_motion_plan_falls_back_on_unrecognized_preset_name(self):
        scene_motion = SceneMotion(
            preset_name="not_a_real_preset",
            scale=ScaleRange(start=1.0, end=1.0),
            position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.5, y_end=0.5),
        )
        motion_plan = _scene_motion_to_motion_plan(scene_motion, duration=2.0)
        self.assertIsInstance(motion_plan.preset, MotionPresetName)

    def test_scene_motion_to_motion_plan_falls_back_when_preset_name_is_none(self):
        scene_motion = SceneMotion(
            scale=ScaleRange(start=1.0, end=1.0),
            position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.5, y_end=0.5),
        )
        self.assertIsNone(scene_motion.preset_name)
        motion_plan = _scene_motion_to_motion_plan(scene_motion, duration=2.0)
        self.assertIsInstance(motion_plan.preset, MotionPresetName)

    def test_render_composition_rejects_empty_scene_list_without_touching_service(self):
        plan = CompositionPlan(scenes=[])
        mock_service = Mock()
        with self.assertRaises(ValidationError):
            render_composition(plan, {}, mock_service)
        mock_service.create_job.assert_not_called()

    def test_compute_scene_start_times_first_scene_starts_at_zero(self):
        scenes = [
            _make_scene("scene_01", 1, 2.0, asset_id=101),
            _make_scene("scene_02", 2, 2.0, asset_id=102),
        ]
        starts = _compute_scene_start_times(scenes, transition_duration=0.5)
        self.assertEqual(starts["scene_01"], 0.0)

    def test_compute_scene_start_times_accounts_for_transition_overlap(self):
        scenes = [
            _make_scene("scene_01", 1, 2.0, asset_id=101),
            _make_scene("scene_02", 2, 2.0, asset_id=102),
        ]
        starts = _compute_scene_start_times(scenes, transition_duration=0.5)
        # scene_02 starts at scene_01's duration minus the transition overlap.
        self.assertAlmostEqual(starts["scene_02"], 1.5)

    def test_compute_scene_start_times_empty_scenes_returns_empty(self):
        self.assertEqual(_compute_scene_start_times([], transition_duration=0.5), {})

    def test_build_sfx_cues_only_includes_scenes_with_sfx(self):
        scenes = [
            _make_scene("scene_01", 1, 1.0, asset_id=101),
            Scene(
                id="scene_02",
                order=2,
                duration=1.0,
                source_asset_id=102,
                motion=_default_motion(),
                audio=SceneAudio(sfx="/path/to/effect.mp3", sfx_volume=0.6),
                output_format=OutputFormat(width=320, height=568),
            ),
        ]
        cues = _build_sfx_cues(scenes, transition_duration=0.3)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0]["path"], "/path/to/effect.mp3")
        self.assertEqual(cues[0]["volume"], 0.6)

    def test_build_sfx_cues_missing_optional_sfx_returns_empty_list(self):
        scenes = [_make_scene("scene_01", 1, 1.0, asset_id=101)]
        self.assertEqual(_build_sfx_cues(scenes, transition_duration=0.3), [])


class PreflightValidationTests(unittest.TestCase):
    """A missing/unresolvable asset on a *later* scene must be caught
    before any earlier scene is rendered -- see
    docs/features/35-multi-beat-composition.md. No ffmpeg needed: these
    tests prove no rendering was even attempted, via a mocked renderer and
    a mocked service (so it's fine to run unconditionally, unlike the
    FFMPEG_AVAILABLE-gated integration tests above).
    """

    def test_missing_asset_mapping_on_third_of_three_scenes_renders_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image1 = _make_solid_image(tmp_path / "a.jpg", color=(200, 40, 40))
            image2 = _make_solid_image(tmp_path / "b.jpg", color=(40, 200, 40))
            plan = CompositionPlan(
                scenes=[
                    _make_scene("scene_01", 1, 1.0, asset_id=101),
                    _make_scene("scene_02", 2, 1.0, asset_id=102),
                    _make_scene("scene_03", 3, 1.0, asset_id=103),
                ]
            )
            mock_service = Mock()
            asset_paths = {101: str(image1), 102: str(image2)}  # 103 (scene_03) intentionally missing
            with patch("app.api.v1.endpoints.composition_render.render_motion_clip") as mock_render:
                with self.assertRaises(ValidationError) as ctx:
                    render_composition(plan, asset_paths, mock_service)
            self.assertIn("Beat 3", str(ctx.exception))
            mock_render.assert_not_called()
            mock_service.create_job.assert_not_called()

    def test_asset_file_missing_on_disk_for_third_of_three_scenes_renders_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image1 = _make_solid_image(tmp_path / "a.jpg", color=(200, 40, 40))
            image2 = _make_solid_image(tmp_path / "b.jpg", color=(40, 200, 40))
            plan = CompositionPlan(
                scenes=[
                    _make_scene("scene_01", 1, 1.0, asset_id=101),
                    _make_scene("scene_02", 2, 1.0, asset_id=102),
                    _make_scene("scene_03", 3, 1.0, asset_id=103),
                ]
            )
            mock_service = Mock()
            asset_paths = {101: str(image1), 102: str(image2), 103: str(tmp_path / "does_not_exist.jpg")}
            with patch("app.api.v1.endpoints.composition_render.render_motion_clip") as mock_render:
                with self.assertRaises(FileOperationError) as ctx:
                    render_composition(plan, asset_paths, mock_service)
            self.assertIn("Beat 3", str(ctx.exception))
            mock_render.assert_not_called()
            mock_service.create_job.assert_not_called()


# -- Task 10: expanded preflight (audio/captions/runtime) + render profile ----


class ExpandedPreflightChecksTests(unittest.TestCase):
    """Task 10 hardening (docs/features/37-e2e-pipeline-hardening.md) widens
    preflight from "asset files exist" (above) to also cover background
    music, caption fonts, and the ffmpeg/ffprobe/output-dir runtime -- all
    checked, and rendering blocked, before any expensive work starts. Each
    scenario here is otherwise a valid, renderable plan (real images, no
    missing assets) so only the one thing under test can be the failure
    cause.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.image1 = _make_solid_image(self.tmp_path / "a.jpg", color=(200, 40, 40))
        self.plan = CompositionPlan(scenes=[_make_scene("scene_01", 1, 1.0, asset_id=101)])
        self.asset_paths = {101: str(self.image1)}
        self.mock_service = Mock()
        self.mock_service.job_dir.return_value = self.tmp_path / "job_dir"

    def tearDown(self):
        self.tmpdir.cleanup()

    def _render(self, **kwargs):
        with patch("app.api.v1.endpoints.composition_render.render_motion_clip"):
            return render_composition(self.plan, self.asset_paths, self.mock_service, **kwargs)

    def test_missing_background_music_file_blocks_render_with_missing_audio_code(self):
        self.plan.music_path = str(self.tmp_path / "does_not_exist.mp3")
        with self.assertRaises(FileOperationError) as ctx:
            self._render()
        self.assertIn("MISSING_AUDIO", str(ctx.exception))
        self.mock_service.create_job.assert_not_called()

    def test_missing_ffmpeg_binary_blocks_render_with_ffmpeg_not_found_code(self):
        with patch("app.api.v1.endpoints.composition_render.shutil.which", side_effect=lambda name: None if name == "ffmpeg" else "/usr/bin/ffprobe"):
            with self.assertRaises(FileOperationError) as ctx:
                self._render()
        self.assertIn("FFMPEG_NOT_FOUND", str(ctx.exception))
        self.mock_service.create_job.assert_not_called()

    def test_missing_ffprobe_binary_blocks_render_with_ffprobe_not_found_code(self):
        with patch("app.api.v1.endpoints.composition_render.shutil.which", side_effect=lambda name: None if name == "ffprobe" else "/usr/bin/ffmpeg"):
            with self.assertRaises(FileOperationError) as ctx:
                self._render()
        self.assertIn("FFPROBE_NOT_FOUND", str(ctx.exception))
        self.mock_service.create_job.assert_not_called()

    def test_missing_caption_font_blocks_render_with_invalid_caption_config_code(self):
        with patch("app.api.v1.endpoints.composition_render.FONT_PATH", "C:/does/not/exist/arial.ttf"):
            with patch("app.api.v1.endpoints.composition_render.FONT_PATH_BOLD", "C:/does/not/exist/arialbd.ttf"):
                with self.assertRaises(FileOperationError) as ctx:
                    self._render()
        self.assertIn("INVALID_CAPTION_CONFIG", str(ctx.exception))
        self.mock_service.create_job.assert_not_called()

    def test_unwritable_output_dir_blocks_render_with_output_dir_not_writable_code(self):
        unwritable_marker = self.tmp_path / "no_write_here"
        with patch("app.api.v1.endpoints.composition_render.Path.mkdir", side_effect=OSError("permission denied")):
            with self.assertRaises(FileOperationError) as ctx:
                self._render(output_dir=str(unwritable_marker))
        self.assertIn("OUTPUT_DIR_NOT_WRITABLE", str(ctx.exception))
        self.mock_service.create_job.assert_not_called()

    def test_valid_plan_with_no_music_and_real_binaries_passes_preflight(self):
        # Sanity check for the tests above: a plan with nothing wrong at all
        # must NOT raise, proving the checks above are each catching a real
        # problem and not just always failing.
        job_id = self._render()
        self.assertIsNotNone(job_id)
        self.mock_service.create_job.assert_called_once()


class RenderProfileWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.image1 = _make_solid_image(self.tmp_path / "a.jpg", color=(200, 40, 40))
        # Scene deliberately uses a small, non-profile resolution (as the
        # rest of this test suite's fixtures do, for fast test renders) --
        # proves the render profile is validated/recorded, not force-applied
        # over a caller's own explicit Scene.output_format.
        self.plan = CompositionPlan(scenes=[_make_scene("scene_01", 1, 1.0, asset_id=101, width=320, height=568)])
        self.asset_paths = {101: str(self.image1)}
        self.mock_service = Mock()
        self.mock_service.job_dir.return_value = self.tmp_path / "job_dir"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_unknown_profile_name_raises_validation_error_before_any_rendering(self):
        with patch("app.api.v1.endpoints.composition_render.render_motion_clip") as mock_render:
            with self.assertRaises(ValidationError):
                render_composition(self.plan, self.asset_paths, self.mock_service, profile="CINEMA_4K")
        mock_render.assert_not_called()
        self.mock_service.create_job.assert_not_called()

    def test_known_profile_does_not_override_scenes_own_output_format(self):
        with patch("app.api.v1.endpoints.composition_render.render_motion_clip"):
            render_composition(self.plan, self.asset_paths, self.mock_service, profile="SOCIAL_VERTICAL")
        # SOCIAL_VERTICAL is 1080x1920 -- the scene's own 320x568 must
        # survive untouched (see render_composition's own docstring for why).
        self.assertEqual(self.plan.scenes[0].output_format.width, 320)
        self.assertEqual(self.plan.scenes[0].output_format.height, 568)

    def test_known_profile_name_is_passed_through_to_create_job(self):
        with patch("app.api.v1.endpoints.composition_render.render_motion_clip"):
            render_composition(self.plan, self.asset_paths, self.mock_service, profile="PREVIEW")
        _, kwargs = self.mock_service.create_job.call_args
        self.assertEqual(kwargs["render_profile"], "PREVIEW")
        self.assertIsInstance(kwargs["preflight_seconds"], float)


if __name__ == "__main__":
    unittest.main()
