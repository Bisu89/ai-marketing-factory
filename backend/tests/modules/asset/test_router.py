"""Tests for the one piece of real logic in app/modules/asset/router.py:
GET /assets/{id}/file -- a generic "give me the bytes to preview" route,
originally built for image previews (Task 32) and, since Task 36, also
used for audio previews (narration/music asset pickers) -- not type-
restricted, unlike app.modules.beat's motion-render path (get_image()),
where only an image can actually be rendered. The other routes are thin
wrappers over already-tested AssetService methods. Route handlers are
called directly as plain functions, matching this codebase's established
test convention (no TestClient anywhere in this suite).
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.exceptions import FileOperationError, NotFoundError
from app.db.base import Base
from app.modules.asset.models import Asset
from app.modules.asset.router import get_asset_file
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService


class GetAssetFileTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine, tables=[Asset.__table__])
        self.db = Session(bind=self.engine)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service = AssetService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _register_image(self, name: str = "photo.jpg") -> Asset:
        file_path = self.tmp_path / name
        file_path.write_bytes(b"fake-jpeg-bytes")
        return self.service.register(AssetRegisterIn(filename=name, path=str(file_path), type="image"))

    def test_existing_image_asset_returns_a_file_response(self):
        asset = self._register_image()
        response = get_asset_file(asset.id, self.service)
        self.assertIsInstance(response, FileResponse)
        self.assertEqual(Path(response.path), Path(asset.path))

    def test_missing_asset_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            get_asset_file(999, self.service)

    def test_non_image_asset_is_served_too(self):
        # Audio (and any other registered type) must be previewable, not
        # just images -- see docs/features/36-audio-pipeline.md's
        # narration/music asset pickers.
        file_path = self.tmp_path / "voice.mp3"
        file_path.write_bytes(b"fake-mp3-bytes")
        asset = self.service.register(AssetRegisterIn(filename="voice.mp3", path=str(file_path), type="audio"))
        response = get_asset_file(asset.id, self.service)
        self.assertIsInstance(response, FileResponse)
        self.assertEqual(Path(response.path), Path(asset.path))

    def test_asset_row_exists_but_file_deleted_from_disk_raises_file_operation_error(self):
        asset = self._register_image()
        Path(asset.path).unlink()
        with self.assertRaises(FileOperationError):
            get_asset_file(asset.id, self.service)


if __name__ == "__main__":
    unittest.main()
