"""Tests for the single-Beat motion preview adapter
(app/api/v1/endpoints/beat_preview.py): Asset + Beat.motion_preset +
duration -> one MP4 via the existing local motion renderer. The route
handler is called directly as a plain function, matching this codebase's
established test convention (see e.g. tests/api/test_beat_generate.py).
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.beat_preview import BeatPreviewRequest, render_beat_preview
from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class BeatPreviewRequestValidationTests(unittest.TestCase):
    def test_default_motion_preset_is_static(self):
        payload = BeatPreviewRequest(asset_id=1)
        self.assertEqual(payload.motion_preset.value, "STATIC")

    def test_zero_duration_rejected(self):
        with self.assertRaises(PydanticValidationError):
            BeatPreviewRequest(asset_id=1, duration=0.0)

    def test_negative_duration_rejected(self):
        with self.assertRaises(PydanticValidationError):
            BeatPreviewRequest(asset_id=1, duration=-2.0)

    def test_invalid_motion_preset_rejected(self):
        with self.assertRaises(PydanticValidationError):
            BeatPreviewRequest(asset_id=1, motion_preset="KAMEHAMEHA")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class RenderBeatPreviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine, tables=[Asset.__table__])
        self.db = Session(bind=self.engine)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.asset_service = AssetService(self.db)
        self.settings = Settings(library_dir=str(self.tmp_path / "library"))

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _register_image(self, name: str = "photo.jpg") -> Asset:
        file_path = self.tmp_path / name
        Image.new("RGB", (800, 600), color=(30, 120, 200)).save(file_path)
        return self.asset_service.register(AssetRegisterIn(filename=name, path=str(file_path), type="image"))

    def test_renders_a_preview_clip_and_returns_a_media_url(self):
        asset = self._register_image()
        payload = BeatPreviewRequest(asset_id=asset.id, motion_preset="SLOW_PUSH_IN", duration=1.0)

        result = render_beat_preview(payload, self.asset_service, self.settings)

        self.assertTrue(result.preview_media_url.startswith("/media/_beat/previews/"))
        self.assertEqual(result.duration, 1.0)
        self.assertGreater(result.render_time_seconds, 0)

        # /media/<rel> maps back to library_dir/<rel> (see app/main.py's
        # StaticFiles mount and _to_media_url's own inverse in schemas.py).
        rel = result.preview_media_url.removeprefix("/media/")
        output_path = Path(self.settings.library_dir) / rel
        self.assertTrue(output_path.exists())

        probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name,pix_fmt",
                "-show_entries", "format=duration",
                "-of", "json", str(output_path),
            ],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        probe_data = json.loads(probe.stdout)
        stream = probe_data["streams"][0]
        self.assertEqual(stream["width"], result.width)
        self.assertEqual(stream["height"], result.height)
        self.assertEqual(stream["codec_name"], "h264")
        self.assertEqual(stream["pix_fmt"], "yuv420p")
        self.assertAlmostEqual(float(probe_data["format"]["duration"]), 1.0, delta=0.15)

    def test_missing_asset_raises_not_found(self):
        payload = BeatPreviewRequest(asset_id=999, duration=1.0)
        with self.assertRaises(NotFoundError):
            render_beat_preview(payload, self.asset_service, self.settings)

    def test_non_image_asset_rejected(self):
        video_path = self.tmp_path / "clip.mp4"
        video_path.write_bytes(b"fake-mp4-bytes")
        asset = self.asset_service.register(AssetRegisterIn(filename="clip.mp4", path=str(video_path), type="video"))
        payload = BeatPreviewRequest(asset_id=asset.id, duration=1.0)
        with self.assertRaises(ValidationError):
            render_beat_preview(payload, self.asset_service, self.settings)


if __name__ == "__main__":
    unittest.main()
