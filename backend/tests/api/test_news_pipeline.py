"""Integration tests for the News -> Factory composition root
(app/api/v1/endpoints/news_pipeline.py). Route handlers called directly as
plain functions against a shared temp-file SQLite DB; the LLM call is
mocked at the news_pipeline boundary (no network).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints import news_pipeline
from app.api.v1.endpoints.news_pipeline import create_news_batch, draft_scripts
from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.ai.llm_client import LLMCallResult
from app.modules.batch.models import Batch, BatchItem
from app.modules.beat.models import Project
from app.modules.news import service as news_service
from app.modules.news.feeds import FetchedEntry
from app.modules.news.models import NewsItem, NewsSource
from app.modules.news.schemas import DraftScriptsRequest, NewsBatchRequest


def _fake_llm(*args, **kwargs) -> LLMCallResult:
    return LLMCallResult(
        text='{"hook": "Ngân hàng tăng lãi suất.", "body": ["Mức tăng là 0,5 điểm phần trăm.", '
        '"Quyết định có hiệu lực từ hôm nay."], "ending": "Thị trường đang theo dõi sát."}',
        refused=False, provider="anthropic", model="claude-sonnet-5",
        input_tokens=100, output_tokens=50, latency_ms=10,
    )


def _entry(title: str, guid: str) -> FetchedEntry:
    return FetchedEntry(guid=guid, title=title, summary=f"Tóm tắt: {title}", link=f"https://x/{guid}",
                        image_url=None, published_at=None)


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
                NewsSource.__table__, NewsItem.__table__,
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
            _entry("Ngân hàng tăng lãi suất lên 5%", "g1"),
            _entry("Bão số 3 đổ bộ miền Trung", "g2"),
        ]):
            news_service.fetch_source(source.id)
        self.item_ids = [i.id for i in news_service.list_items()[0]]

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def test_draft_scripts_fills_script_text_and_marks_drafted(self):
        with patch("app.api.v1.endpoints.news_pipeline.call_structured", side_effect=_fake_llm):
            res = draft_scripts(DraftScriptsRequest(item_ids=self.item_ids), self.settings)
        self.assertEqual(res.drafted, 2)
        for item in news_service.list_items()[0]:
            self.assertEqual(item.status, "drafted")
            self.assertIn("Ngân hàng tăng lãi suất", item.script_text)

    def test_create_news_batch_requires_a_drafted_script(self):
        with self.assertRaises(ValidationError):
            create_news_batch(
                NewsBatchRequest(name="Tin sáng", template_id="news_vi", item_ids=self.item_ids),
                self.settings,
            )

    def test_create_news_batch_builds_projects_and_queues_items(self):
        with patch("app.api.v1.endpoints.news_pipeline.call_structured", side_effect=_fake_llm):
            draft_scripts(DraftScriptsRequest(item_ids=self.item_ids), self.settings)

        batch = create_news_batch(
            NewsBatchRequest(name="Tin sáng", template_id="news_vi", item_ids=self.item_ids),
            self.settings,
        )
        self.assertEqual(len(batch.items), 2)
        self.assertTrue(all(i.status == "PROJECT_CREATED" for i in batch.items))

        for item in news_service.list_items()[0]:
            self.assertEqual(item.status, "queued")
            self.assertEqual(item.batch_id, batch.id)
            self.assertIsNotNone(item.project_id)

        # The project's script_text is the drafted news script, and locked
        # against the Factory CONTENT stage (non-blank script_text is the
        # skip condition).
        db = self.TestSessionLocal()
        try:
            project = db.query(Project).first()
            self.assertIn("Ngân hàng", project.beat_plan_json["script_text"])
        finally:
            db.close()

    def test_unknown_template_is_rejected(self):
        with patch("app.api.v1.endpoints.news_pipeline.call_structured", side_effect=_fake_llm):
            draft_scripts(DraftScriptsRequest(item_ids=self.item_ids), self.settings)
        from app.core.exceptions import NotFoundError

        with self.assertRaises(NotFoundError):
            create_news_batch(
                NewsBatchRequest(name="x", template_id="does_not_exist", item_ids=self.item_ids),
                self.settings,
            )
