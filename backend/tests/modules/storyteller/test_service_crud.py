"""Episode/asset CRUD against a real temp-file SQLite DB (SessionLocal
patched). No edge_tts, no ffmpeg -- narration/compositing are exercised
separately in test_composite.py / manually."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.storyteller import service
from app.modules.storyteller.models import StorytellerAsset, StorytellerEpisode
from app.modules.storyteller.schemas import EpisodeCreateIn


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

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe not found on PATH")
    def test_save_asset_music_kind_is_probed_as_audio(self):
        tmp_upload = Path(self.tmp.name) / "upload.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-t", "2", "-i", "sine=frequency=220:duration=2",
             "-c:a", "libmp3lame", str(tmp_upload)],
            check=True,
        )
        asset = service.save_asset(
            kind="music", name="drone", tmp_upload_path=tmp_upload, library_dir=Path(self.tmp.name),
        )
        self.assertEqual(asset.media_type, "audio")
        self.assertIsNone(asset.width)
        self.assertIsNone(asset.key_color)
        self.assertAlmostEqual(asset.duration_sec, 2.0, delta=0.2)

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

    def test_slide_asset_ids_round_trips_through_the_json_column(self):
        ep = self._make(layout="slideshow", slide_asset_ids=[3, 1, 2])
        fetched = service.get_episode(ep.id)
        self.assertEqual(fetched.slide_asset_ids, [3, 1, 2])

    def test_music_asset_id_round_trips(self):
        ep = self._make(music_asset_id=7)
        fetched = service.get_episode(ep.id)
        self.assertEqual(fetched.music_asset_id, 7)


class EpisodeCreateInValidationTests(unittest.TestCase):
    def _payload(self, **overrides):
        fields = dict(title="T", script_text="hello world")
        fields.update(overrides)
        return fields

    def test_slideshow_requires_at_least_two_slide_asset_ids(self):
        with self.assertRaises(PydanticValidationError):
            EpisodeCreateIn(**self._payload(layout="slideshow", slide_asset_ids=[1]))
        with self.assertRaises(PydanticValidationError):
            EpisodeCreateIn(**self._payload(layout="slideshow"))

    def test_slideshow_with_enough_images_is_accepted(self):
        payload = EpisodeCreateIn(**self._payload(layout="slideshow", slide_asset_ids=[1, 2, 3]))
        self.assertEqual(payload.slide_asset_ids, [1, 2, 3])

    def test_non_slideshow_layouts_ignore_slide_asset_ids(self):
        payload = EpisodeCreateIn(**self._payload(layout="single"))
        self.assertIsNone(payload.slide_asset_ids)


if __name__ == "__main__":
    unittest.main()
