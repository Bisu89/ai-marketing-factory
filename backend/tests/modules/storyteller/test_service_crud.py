"""Episode/asset CRUD against a real temp-file SQLite DB (SessionLocal
patched). No edge_tts, no ffmpeg -- narration/compositing are exercised
separately in test_composite.py / manually."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.storyteller import service
from app.modules.storyteller.models import StorytellerAsset, StorytellerEpisode


class StorytellerServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.tmp.name) / 'd.db'}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(
            bind=self.engine, tables=[StorytellerEpisode.__table__, StorytellerAsset.__table__]
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._patcher = patch("app.modules.storyteller.service.SessionLocal", self.SessionLocal)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.engine.dispose()
        self.tmp.cleanup()

    def _make(self, **overrides):
        fields = dict(
            title="Chuong 1", script_text="Ngay xua co mot...", voice="vi-VN-HoaiMyNeural",
            narration_rate="+0%", burn_captions=True, background_asset_id=None, avatar_asset_id=None,
        )
        fields.update(overrides)
        return service.create_episode(**fields)

    def test_create_episode_computes_word_count(self):
        ep = self._make(script_text="mot hai ba bon nam")
        self.assertEqual(ep.word_count, 5)
        self.assertEqual(ep.status, "pending")

    def test_get_missing_episode_raises(self):
        with self.assertRaises(NotFoundError):
            service.get_episode(9999)

    def test_list_episodes_newest_first(self):
        a = self._make(title="A")
        b = self._make(title="B")
        rows = service.list_episodes()
        self.assertEqual([r.id for r in rows][:2], [b.id, a.id])

    def test_retry_resets_failed_episode(self):
        ep = self._make()
        db = self.SessionLocal()
        row = db.get(StorytellerEpisode, ep.id)
        row.status = "failed"
        row.error_message = "boom"
        db.commit()
        db.close()

        retried = service.retry_episode(ep.id)
        self.assertEqual(retried.status, "pending")
        self.assertIsNone(retried.error_message)

    def test_retry_in_progress_episode_rejected(self):
        ep = self._make()
        db = self.SessionLocal()
        row = db.get(StorytellerEpisode, ep.id)
        row.status = "narrating"
        db.commit()
        db.close()
        with self.assertRaises(ValidationError):
            service.retry_episode(ep.id)

    def test_delete_episode_removes_row_and_directory(self):
        ep = self._make()
        episode_dir = Path(self.tmp.name) / "storyteller" / "episodes" / str(ep.id)
        episode_dir.mkdir(parents=True)
        (episode_dir / "final.mp4").write_bytes(b"fake")

        service.delete_episode(ep.id, Path(self.tmp.name))

        with self.assertRaises(NotFoundError):
            service.get_episode(ep.id)
        self.assertFalse(episode_dir.exists())

    def test_list_assets_filters_by_kind(self):
        db = self.SessionLocal()
        db.add(StorytellerAsset(kind="background", name="bg1", path="/x/bg1.mp4"))
        db.add(StorytellerAsset(kind="avatar", name="av1", path="/x/av1.mp4", key_color="0x00FF00"))
        db.commit()
        db.close()

        self.assertEqual(len(service.list_assets("background")), 1)
        self.assertEqual(len(service.list_assets("avatar")), 1)
        self.assertEqual(len(service.list_assets()), 2)

    def test_delete_asset_removes_row(self):
        db = self.SessionLocal()
        asset = StorytellerAsset(kind="background", name="bg1", path=str(Path(self.tmp.name) / "bg1.mp4"))
        db.add(asset)
        db.commit()
        db.refresh(asset)
        asset_id = asset.id
        db.close()
        Path(self.tmp.name, "bg1.mp4").write_bytes(b"x")

        service.delete_asset(asset_id, Path(self.tmp.name))
        self.assertEqual(service.list_assets(), [])


if __name__ == "__main__":
    unittest.main()
