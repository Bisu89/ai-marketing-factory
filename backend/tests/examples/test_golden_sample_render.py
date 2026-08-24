"""The Task 10 final acceptance test: actually renders the Task 09.5 golden
sample (examples/video_factory/) through the real pipeline --
render_composition() [composition_render.py] -> VideoComposerService._run_job
[video_composer/service.py], i.e. real ffmpeg motion rendering (Task 06),
real merge-with-transitions, real subtitle generation (Task 08's caption
presets), real audio mixing (narration + ducked music), real finalize --
then verifies the result with ffprobe: duration, resolution, fps, video
codec, audio codec, and that a render_metadata.json sidecar was written.

Only TTS narration is mocked (edge_tts is a real Microsoft network call --
see tests/api/test_composition_render.py's identical convention); every
other step is the real, unmodified pipeline built across Tasks 06-08.
"""

import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import selectinload, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.composition_render import render_beats_for_job, render_composition
from app.db.base import Base
from app.modules.composition.schemas import CompositionPlan
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob
from app.modules.video_composer.service import VideoComposerService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
EXAMPLE_DIR = Path(__file__).resolve().parents[3] / "examples" / "video_factory"
REPO_ROOT = EXAMPLE_DIR.parents[1]


def _fake_run_narration(script_text: str, voice: str, output_path: Path, rate: str = "+0%") -> list[dict]:
    subprocess.run(
        [
            "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "2.0",
            "-c:a", "libmp3lame", str(output_path),
        ],
        check=True, stdin=subprocess.DEVNULL,
    )
    return [{"start": 0.0, "end": 0.6, "text": "Meet"}, {"start": 0.6, "end": 1.2, "text": "Anna"}]


def _ffprobe_json(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return json.loads(result.stdout)


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class GoldenSampleRenderAcceptanceTest(unittest.TestCase):
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

    def test_golden_sample_renders_to_a_valid_playable_final_mp4(self):
        plan = CompositionPlan.model_validate(json.loads((EXAMPLE_DIR / "composition.json").read_text(encoding="utf-8")))
        assets_data = json.loads((EXAMPLE_DIR / "assets.json").read_text(encoding="utf-8"))
        asset_paths = {entry["id"]: str(REPO_ROOT / entry["path"]) for entry in assets_data}

        music_path = REPO_ROOT / "examples" / "video_factory" / "assets" / "background_music.mp3"
        self.assertTrue(music_path.exists(), "background_music.mp3 must exist for a real render")
        # composition.json's music_path is repo-relative (see
        # docs/features/27-video-factory-golden-sample.md); ffmpeg resolves
        # paths against its own process working directory, not the repo
        # root, so it must be made absolute before an actual render.
        plan = plan.model_copy(update={"music_path": str(music_path)})

        # Same story for beat_01's SFX cue: composition.json's "whoosh_in.mp3"
        # is a bare, symbolic filename (Task 09.5 never intended it to be a
        # real resolvable file, since that task explicitly did no
        # rendering) -- point it at a real placeholder for this real render.
        sfx_path = REPO_ROOT / "examples" / "video_factory" / "assets" / "whoosh_in.mp3"
        self.assertTrue(sfx_path.exists(), "whoosh_in.mp3 must exist for a real render")
        scenes = list(plan.scenes)
        first_scene = scenes[0]
        scenes[0] = first_scene.model_copy(update={"audio": first_scene.audio.model_copy(update={"sfx": str(sfx_path)})})
        plan = plan.model_copy(update={"scenes": scenes})

        with patch.object(self.service, "_run_narration", side_effect=_fake_run_narration):
            wall_clock_start = time.monotonic()
            job_id = render_composition(plan, asset_paths, self.service, title="Golden Sample Acceptance Render")
            self.service._run_job(job_id)
            wall_clock_elapsed = time.monotonic() - wall_clock_start

        job = self._get_job(job_id)
        self.assertEqual(job.status, "completed", msg=job.error_message)
        self.assertEqual(len(job.clips), 5)

        output_path = Path(job.output_path)
        self.assertTrue(output_path.exists())

        # -- ffprobe verification (this task's literal acceptance list) -----
        probe = _ffprobe_json(output_path)
        video_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        audio_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")

        self.assertEqual(video_stream["codec_name"], "h264")
        self.assertEqual(video_stream["width"], 1080)
        self.assertEqual(video_stream["height"], 1920)
        self.assertEqual(video_stream["r_frame_rate"], "30/1")
        self.assertEqual(audio_stream["codec_name"], "aac")

        output_duration = float(probe["format"]["duration"])
        # 5 scenes (4+8+8+6+4=30s) with 4 crossfade transitions @ 0.4s
        # overlap each -- the same overlap formula
        # _merge_clips_with_transitions itself uses, reproduced here as a
        # plain float computation, not an import.
        expected_duration = 4.0 + (8.0 - 0.4) + (8.0 - 0.4) + (6.0 - 0.4) + (4.0 - 0.4)
        self.assertAlmostEqual(output_duration, expected_duration, delta=0.3)

        # -- audio/video sync: -shortest muxing in _finalize means the
        # container's overall duration is only trustworthy as a sync proof
        # if the audio track itself is at least that long, not silently
        # truncated shorter than the video.
        audio_duration_raw = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(output_path),
            ],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        ).stdout.strip()
        if audio_duration_raw:
            self.assertAlmostEqual(float(audio_duration_raw), output_duration, delta=0.3)

        # -- render metadata sidecar -----------------------------------------
        metadata_path = output_path.with_name("render_metadata.json")
        self.assertTrue(metadata_path.exists())
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["render_mode"], "local")
        self.assertEqual(metadata["ai_cost"], 0.0)
        self.assertGreater(metadata["render_time_seconds"], 0)
        self.assertAlmostEqual(metadata["duration"], output_duration, delta=0.5)
        self.assertGreater(metadata["output_size_mb"], 0)
        self.assertEqual(metadata["width"], 1080)
        self.assertEqual(metadata["height"], 1920)
        self.assertEqual(metadata["fps"], 30)
        self.assertEqual(metadata["clip_count"], 5)

        output_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(
            f"\n[golden sample acceptance] wall_clock={wall_clock_elapsed:.1f}s "
            f"reported_render_time={metadata['render_time_seconds']}s "
            f"output_duration={output_duration:.2f}s size={output_size_mb:.2f}MB "
            f"resolution={video_stream['width']}x{video_stream['height']} "
            f"fps={video_stream['r_frame_rate']} "
            f"video_codec={video_stream['codec_name']} audio_codec={audio_stream['codec_name']}"
        )


if __name__ == "__main__":
    unittest.main()
