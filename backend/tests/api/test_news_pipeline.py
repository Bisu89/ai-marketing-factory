"""Integration tests for the News -> Factory composition root
(app/api/v1/endpoints/news_pipeline.py). Route handlers called directly as
plain functions against a shared temp-file SQLite DB; LLM calls and image
downloads are mocked at the news_pipeline boundary (no network).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.news_pipeline import create_news_batch, create_news_digest, draft_scripts
from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.ai.llm_client import LLMCallResult
from app.modules.asset.models import Asset
from app.modules.batch.models import Batch, BatchItem
from app.modules.beat.models import Project
from app.modules.news import service as news_service
from app.modules.news.feeds import FetchedEntry
from app.modules.news.models import NewsItem, NewsSource
from app.modules.news.schemas import DraftScriptsRequest, NewsBatchRequest, NewsDigestRequest


def _fake_script_llm(*args, **kwargs) -> LLMCallResult:
    return LLMCallResult(
        text='{"hook": "Ngân hàng tăng lãi suất.", "body": ["Mức tăng là 0,5 điểm phần trăm.", '
        '"Quyết định có hiệu lực từ hôm nay."], "ending": "Thị trường đang theo dõi sát."}',
        refused=False, provider="anthropic", model="claude-sonnet-5",
        input_tokens=100, output_tokens=50, latency_ms=10,
    )


def _fake_digest_llm(*args, **kwargs) -> LLMCallResult:
    return LLMCallResult(
        text='{"intro": "Điểm tin hôm nay.", "segments": [{"narration": "Tin một xảy ra."}, '
        '{"narration": "Tin hai xảy ra."}], "outro": "Cảm ơn đã theo dõi."}',
        refused=False, provider="anthropic", model="claude-sonnet-5",
        input_tokens=100, output_tokens=80, latency_ms=10,
    )


def _entry(title: str, guid: str, image_url: str | None = None) -> FetchedEntry:
    return FetchedEntry(guid=guid, title=title, summary=f"Tóm tắt: {title}", link=f"https://x/{guid}",
                        image_url=image_url, published_at=None)


class NewsPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.db_path = self.tmp_path / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False, "timeout": 30}
        )
        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                NewsSource.__table__, NewsItem.__table__, Asset.__table__,
                Batch.__table__, BatchItem.__table__, Project.__table__,
            ],
        )
        self.TestSessionLocal = sessionmaker(bind=self.engine)
        self.patchers = [
            patch("app.modules.news.service.SessionLocal", self.TestSessionLocal),
            patch("app.modules.batch.service.SessionLocal", self.TestSessionLocal),
            patch("app.modules.beat.project_service.SessionLocal", self.TestSessionLocal),
            patch("app.api.v1.endpoints.news_pipeline.SessionLocal", self.TestSessionLocal),
        ]
        for p in self.patchers:
            p.start()

        self.settings = Settings(
            library_dir=str(self.tmp_path), anthropic_api_key="fake-test-key",
            ai_provider="anthropic", openai_api_key=None,
        )
        source = news_service.create_source(
            name="VnExpress", feed_url="https://vnexpress.net/rss/tin-moi-nhat.rss",
            category="Tổng hợp", language="vi", enabled=True,
        )
        with patch("app.modules.news.service.fetch_feed", return_value=[
            _entry("Ngân hàng tăng lãi suất lên 5%", "g1", image_url="https://x/g1.jpg"),
            _entry("Bão số 3 đổ bộ miền Trung", "g2", image_url="https://x/g2.jpg"),
        ]):
            news_service.fetch_source(source.id)
        self.item_ids = [i.id for i in news_service.list_items()[0]]

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _fake_prepare_image(self, url, dest_path, width, height, **kw):
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(b"\xff\xd8\xff\xd9")  # not a real JPEG, just a file that exists
        return True

    # -- draft-scripts ------------------------------------------------------

    def test_draft_scripts_fills_script_text_and_marks_drafted(self):
        with patch("app.api.v1.endpoints.news_pipeline.call_structured", side_effect=_fake_script_llm):
            res = draft_scripts(DraftScriptsRequest(item_ids=self.item_ids), self.settings)
        self.assertEqual(res.drafted, 2)
        for item in news_service.list_items()[0]:
            self.assertEqual(item.status, "drafted")
            self.assertIn("Ngân hàng tăng lãi suất", item.script_text)

    # -- /news/batch ------------------------------------------------------

    def test_create_news_batch_requires_a_drafted_script(self):
        with self.assertRaises(ValidationError):
            create_news_batch(
                NewsBatchRequest(name="Tin sáng", template_id="news_vi", item_ids=self.item_ids),
                self.settings,
            )

    def test_create_news_batch_without_images_falls_back_to_project_created(self):
        with patch("app.api.v1.endpoints.news_pipeline.call_structured", side_effect=_fake_script_llm):
            draft_scripts(DraftScriptsRequest(item_ids=self.item_ids), self.settings)
        # image download disabled -> plain script projects, Generate Beats later
        batch = create_news_batch(
            NewsBatchRequest(name="Tin sáng", template_id="news_vi", item_ids=self.item_ids, use_article_image=False),
            self.settings,
        )
        self.assertEqual(len(batch.items), 2)
        self.assertTrue(all(i.status == "PROJECT_CREATED" for i in batch.items))
        for item in news_service.list_items()[0]:
            self.assertEqual(item.status, "queued")
            self.assertEqual(item.batch_id, batch.id)

    def test_create_news_batch_with_article_image_prebuilds_beats(self):
        with patch("app.api.v1.endpoints.news_pipeline.call_structured", side_effect=_fake_script_llm):
            draft_scripts(DraftScriptsRequest(item_ids=self.item_ids), self.settings)
        with patch("app.api.v1.endpoints.news_pipeline.prepare_article_image", side_effect=self._fake_prepare_image):
            batch = create_news_batch(
                NewsBatchRequest(name="Tin sáng", template_id="news_vi", item_ids=self.item_ids),
                self.settings,
            )
        self.assertTrue(all(i.status == "BEATS_READY" for i in batch.items))

        db = self.TestSessionLocal()
        try:
            for project in db.query(Project).all():
                beats = project.beat_plan_json["beats"]
                self.assertGreaterEqual(len(beats), 1)
                self.assertTrue(all(b["asset_id"] is not None for b in beats))
            # every beat asset is a real news_image Asset
            assets = db.query(Asset).all()
            self.assertTrue(assets and all(a.source == "news_image" for a in assets))
        finally:
            db.close()

    def test_unknown_template_is_rejected(self):
        with patch("app.api.v1.endpoints.news_pipeline.call_structured", side_effect=_fake_script_llm):
            draft_scripts(DraftScriptsRequest(item_ids=self.item_ids), self.settings)
        with self.assertRaises(NotFoundError):
            create_news_batch(
                NewsBatchRequest(name="x", template_id="does_not_exist", item_ids=self.item_ids),
                self.settings,
            )

    # -- /news/digest ---------------------------------------------------

    def test_create_news_digest_builds_one_project_with_a_beat_per_segment(self):
        with patch("app.api.v1.endpoints.news_pipeline.call_structured", side_effect=_fake_digest_llm), \
             patch("app.api.v1.endpoints.news_pipeline.prepare_article_image", side_effect=self._fake_prepare_image):
            batch = create_news_digest(
                NewsDigestRequest(name="Điểm tin sáng", template_id="news_vi", item_ids=self.item_ids),
                self.settings,
            )
        self.assertEqual(len(batch.items), 1)
        self.assertEqual(batch.items[0].status, "BEATS_READY")

        # both source items point at the one digest project
        items = news_service.list_items()[0]
        self.assertTrue(all(i.status == "queued" for i in items))
        self.assertEqual(len({i.project_id for i in items}), 1)

        db = self.TestSessionLocal()
        try:
            project = db.query(Project).first()
            beats = project.beat_plan_json["beats"]
            # intro + 2 segments + outro
            self.assertEqual(len(beats), 4)
            self.assertEqual(beats[0]["type"], "HOOK")
            self.assertEqual(beats[-1]["type"], "ENDING")
            self.assertIn("Điểm tin hôm nay", project.beat_plan_json["script_text"])
        finally:
            db.close()

    def test_digest_requires_at_least_two_items(self):
        with self.assertRaises(ValidationError):
            create_news_digest(
                NewsDigestRequest(name="x", template_id="news_vi", item_ids=[self.item_ids[0], self.item_ids[0]]),
                self.settings,
            )
