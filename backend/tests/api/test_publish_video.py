"""Integration tests for the YouTube publish composition root
(app/api/v1/endpoints/publish_video.py). The upload thread is patched to
run synchronously; the YouTube HTTP calls are patched -- no network.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints import publish_video
from app.api.v1.endpoints.publish_video import upload_to_youtube
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.beat.models import Project
from app.modules.beat.schemas import Beat, BeatPlan, BeatType
from app.modules.publishing import service as pub_service
from app.modules.publishing.models import YouTubeChannel, YouTubeUploadJob
from app.modules.publishing.schemas import UploadRequest
from app.modules.publishing.youtube_client import TokenResponse
from app.modules.video_composer.models import VideoComposeJob

_FRESH_TOKEN = TokenResponse(access_token="at", refresh_token=None, expires_in=3600)


def _plan_json(name: str) -> dict:
    return BeatPlan(
        script_text="x", project_name=name,
        beats=[Beat(id="b1", order=1, type=BeatType.HOOK, narration="n", duration=3.0)],
    ).model_dump(mode="json")


class PublishVideoTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.engine = create_engine(
            f"sqlite:///{self.tmp / 't.db'}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(
            bind=self.engine,
            tables=[YouTubeChannel.__table__, YouTubeUploadJob.__table__, Project.__table__, VideoComposeJob.__table__],
        )
        self.SL = sessionmaker(bind=self.engine)
        self.patchers = [
            patch("app.modules.publishing.service.SessionLocal", self.SL),
            patch("app.modules.beat.project_service.SessionLocal", self.SL),
            patch("app.db.session.SessionLocal", self.SL),
            # run the "background" upload inline for a deterministic test
            patch.object(publish_video, "_start_upload_thread", publish_video._run_upload),
            patch("app.modules.publishing.service.youtube_client.refresh_access_token", return_value=_FRESH_TOKEN),
        ]
        for p in self.patchers:
            p.start()
        self.settings = Settings(google_oauth_client_id="cid", google_oauth_client_secret="sec")

        out = self.tmp / "job_1" / "output"
        out.mkdir(parents=True)
        (out / "final.mp4").write_bytes(b"\x00" * 32)
        (out / "metadata.json").write_text(json.dumps({
            "title": "How France Lost With More Men",
            "description": "Agincourt. #Agincourt #MedievalHistory",
            "hashtags": ["#Agincourt", "#MedievalHistory", "#HenryV"],
        }), encoding="utf-8")
        (out / "thumbnail.jpg").write_bytes(b"\xff\xd8\xff\xd9")

        db = self.SL()
        try:
            job = VideoComposeJob(
                title="Agincourt", script_text="x", status="completed", output_path=str(out / "final.mp4")
            )
            db.add(job)
            db.flush()
            proj = Project(name="Agincourt", slug="agincourt", beat_plan_json=_plan_json("Agincourt"), render_job_id=job.id)
            db.add(proj)
            ch = YouTubeChannel(channel_id="UC1", title="Decisive Battles", refresh_token="rt")
            db.add(ch)
            db.commit()
            self.project_id, self.channel_pk = proj.id, ch.id
        finally:
            db.close()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _upload(self, project_id=None, channel_pk=None, privacy="private"):
        db = self.SL()
        try:
            return upload_to_youtube(
                UploadRequest(
                    project_id=project_id or self.project_id,
                    channel_id=channel_pk or self.channel_pk, privacy=privacy,
                ),
                db=db, settings=self.settings,
            )
        finally:
            db.close()

    def test_upload_sends_metadata_and_thumbnail_then_completes(self):
        with patch.object(publish_video.youtube_client, "upload_video", return_value="VID42") as mock_up, \
             patch.object(publish_video.youtube_client, "set_thumbnail") as mock_thumb:
            res = self._upload()

        job = pub_service.get_upload(res.upload_job_id)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.youtube_video_id, "VID42")
        kwargs = mock_up.call_args.kwargs
        self.assertEqual(kwargs["title"], "How France Lost With More Men")
        self.assertEqual(kwargs["tags"], ["#Agincourt", "#MedievalHistory", "#HenryV"])
        self.assertEqual(kwargs["privacy_status"], "private")
        mock_thumb.assert_called_once()

    def test_duplicate_upload_to_same_channel_is_rejected(self):
        with patch.object(publish_video.youtube_client, "upload_video", return_value="VID1"), \
             patch.object(publish_video.youtube_client, "set_thumbnail"):
            self._upload()
            with self.assertRaises(ValidationError):
                self._upload()

    def test_unrendered_project_is_rejected(self):
        db = self.SL()
        try:
            proj = Project(name="p2", slug="p2", beat_plan_json=_plan_json("p2"), render_job_id=None)
            db.add(proj)
            db.commit()
            pid = proj.id
        finally:
            db.close()
        with self.assertRaises(ValidationError):
            self._upload(project_id=pid)

    def test_upload_failure_lands_on_the_job_row(self):
        with patch.object(publish_video.youtube_client, "upload_video", side_effect=RuntimeError("boom")):
            res = self._upload()
        job = pub_service.get_upload(res.upload_job_id)
        self.assertEqual(job.status, "failed")
        self.assertIn("boom", job.error_message)
