"""Tests for VideoComposeJobOut/job_to_out's render_metadata.json surfacing
(see docs/features/35-multi-beat-composition.md) -- render_time_seconds/
duration/width/height/fps/output_size_mb were written to a JSON sidecar
since Task 10 but never exposed through the API until now.
"""

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.video_composer.models import VideoComposeClip, VideoComposeJob
from app.modules.video_composer.schemas import job_to_out


class JobToOutRenderMetadataTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine, tables=[VideoComposeJob.__table__, VideoComposeClip.__table__])
        self.db = Session(bind=self.engine)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _make_job(self, output_path: Path | None) -> VideoComposeJob:
        job = VideoComposeJob(
            title="Test",
            script_text="",
            status="completed",
            output_path=str(output_path) if output_path else None,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def test_render_metadata_fields_are_surfaced_when_sidecar_exists(self):
        output_path = self.tmp_path / "final.mp4"
        output_path.write_bytes(b"fake-mp4-bytes")
        (self.tmp_path / "render_metadata.json").write_text(
            json.dumps(
                {
                    "render_time_seconds": 8.4,
                    "ai_cost": 0.0,
                    "render_mode": "local",
                    "duration": 23.02,
                    "output_size_mb": 4.1,
                    "width": 1080,
                    "height": 1920,
                    "fps": 30,
                    "clip_count": 5,
                }
            ),
            encoding="utf-8",
        )
        job = self._make_job(output_path)

        out = job_to_out(job, self.tmp_path)

        self.assertEqual(out.render_duration_sec, 23.02)
        self.assertEqual(out.render_width, 1080)
        self.assertEqual(out.render_height, 1920)
        self.assertEqual(out.render_fps, 30)
        self.assertEqual(out.render_time_seconds, 8.4)
        self.assertEqual(out.output_size_mb, 4.1)

    def test_missing_sidecar_degrades_to_none_fields_not_an_error(self):
        output_path = self.tmp_path / "final.mp4"
        output_path.write_bytes(b"fake-mp4-bytes")
        job = self._make_job(output_path)  # no render_metadata.json written

        out = job_to_out(job, self.tmp_path)

        self.assertIsNone(out.render_duration_sec)
        self.assertIsNone(out.render_width)
        self.assertIsNone(out.output_size_mb)

    def test_job_with_no_output_path_yet_degrades_to_none_fields(self):
        job = self._make_job(None)

        out = job_to_out(job, self.tmp_path)

        self.assertIsNone(out.output_media_url)
        self.assertIsNone(out.render_duration_sec)

    def test_corrupt_sidecar_degrades_to_none_fields_not_an_error(self):
        output_path = self.tmp_path / "final.mp4"
        output_path.write_bytes(b"fake-mp4-bytes")
        (self.tmp_path / "render_metadata.json").write_text("{not valid json", encoding="utf-8")
        job = self._make_job(output_path)

        out = job_to_out(job, self.tmp_path)

        self.assertIsNone(out.render_duration_sec)


if __name__ == "__main__":
    unittest.main()
