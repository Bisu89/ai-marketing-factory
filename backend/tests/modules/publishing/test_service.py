"""Service tests for app.modules.publishing.service against a temp-file
SQLite DB. The Google/YouTube HTTP calls are patched -- no network.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.publishing import service
from app.modules.publishing.models import YouTubeChannel, YouTubeUploadJob
from app.modules.publishing.youtube_client import TokenResponse


class _Case(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "t.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(bind=self.engine, tables=[YouTubeChannel.__table__, YouTubeUploadJob.__table__])
        self.SL = sessionmaker(bind=self.engine)
        self.p = patch("app.modules.publishing.service.SessionLocal", self.SL)
        self.p.start()
        self.settings = Settings(
            google_oauth_client_id="cid", google_oauth_client_secret="sec",
        )

    def tearDown(self):
        self.p.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()


class ConnectTests(_Case):
    def test_connect_creates_channel_and_stores_refresh_token(self):
        with patch("app.modules.publishing.service.youtube_client.exchange_code_for_token",
                   return_value=TokenResponse(access_token="at", refresh_token="rt", expires_in=3600)), \
             patch("app.modules.publishing.service.youtube_client.fetch_my_channel",
                   return_value={"id": "UC123", "title": "My Battles", "thumbnail_url": "http://x/a.png"}):
            ch = service.connect_channel_from_code(self.settings, "code")
        self.assertEqual(ch.channel_id, "UC123")
        self.assertEqual(ch.refresh_token, "rt")
        self.assertEqual([c.title for c in service.list_channels()], ["My Battles"])

    def test_reconnect_same_channel_updates_row(self):
        for title in ("Old", "New"):
            with patch("app.modules.publishing.service.youtube_client.exchange_code_for_token",
                       return_value=TokenResponse(access_token="at", refresh_token="rt2", expires_in=3600)), \
                 patch("app.modules.publishing.service.youtube_client.fetch_my_channel",
                       return_value={"id": "UC1", "title": title, "thumbnail_url": None}):
                service.connect_channel_from_code(self.settings, "c")
        channels = service.list_channels()
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0].title, "New")

    def test_connect_without_refresh_token_is_rejected(self):
        with patch("app.modules.publishing.service.youtube_client.exchange_code_for_token",
                   return_value=TokenResponse(access_token="at", refresh_token=None, expires_in=3600)):
            with self.assertRaises(ValidationError):
                service.connect_channel_from_code(self.settings, "c")

    def test_no_oauth_config_is_rejected(self):
        with self.assertRaises(ValidationError):
            service.build_authorize_url(Settings(google_oauth_client_id=None, google_oauth_client_secret=None))


class TokenRefreshTests(_Case):
    def _make_channel(self, expires_in_sec: int) -> int:
        db = self.SL()
        try:
            ch = YouTubeChannel(
                channel_id="UC9", title="C", refresh_token="rt", access_token="old",
                access_token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_sec),
            )
            db.add(ch)
            db.commit()
            return ch.id
        finally:
            db.close()

    def test_valid_token_is_reused(self):
        pk = self._make_channel(3600)
        with patch("app.modules.publishing.service.youtube_client.refresh_access_token") as m:
            token = service.get_fresh_access_token(pk, self.settings)
        self.assertEqual(token, "old")
        m.assert_not_called()

    def test_expiring_token_is_refreshed_and_persisted(self):
        pk = self._make_channel(30)  # inside the margin
        with patch("app.modules.publishing.service.youtube_client.refresh_access_token",
                   return_value=TokenResponse(access_token="new", refresh_token=None, expires_in=3600)):
            token = service.get_fresh_access_token(pk, self.settings)
        self.assertEqual(token, "new")
        self.assertEqual(service.get_channel(pk).access_token, "new")


class UploadJobTests(_Case):
    def _channel(self) -> int:
        db = self.SL()
        try:
            ch = YouTubeChannel(channel_id="UC1", title="C", refresh_token="rt")
            db.add(ch)
            db.commit()
            return ch.id
        finally:
            db.close()

    def test_create_and_transition_upload_job(self):
        pk = self._channel()
        jid = service.create_upload_job(
            channel_pk=pk, project_id=42, render_job_id=7, privacy="private",
            title="T", description="D", video_path="/x/final.mp4",
        )
        self.assertIsNotNone(service.existing_upload(pk, 42))
        service.set_upload_fields(jid, status="completed", youtube_video_id="vid123")
        job = service.get_upload(jid)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.watch_url, "https://www.youtube.com/watch?v=vid123")
        self.assertIsNotNone(job.completed_at)

    def test_reconcile_marks_in_flight_uploads_interrupted(self):
        pk = self._channel()
        j1 = service.create_upload_job(channel_pk=pk, project_id=1, render_job_id=None, privacy="private",
                                       title="a", description="", video_path="/a")
        service.set_upload_fields(j1, status="uploading")
        j2 = service.create_upload_job(channel_pk=pk, project_id=2, render_job_id=None, privacy="private",
                                       title="b", description="", video_path="/b")
        service.set_upload_fields(j2, status="completed")

        service.reconcile_uploads_on_startup()
        self.assertEqual(service.get_upload(j1).status, "interrupted")
        self.assertEqual(service.get_upload(j2).status, "completed")

    def test_get_missing_channel_raises(self):
        with self.assertRaises(NotFoundError):
            service.get_channel(999)
