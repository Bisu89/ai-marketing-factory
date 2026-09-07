"""Tests for app.modules.story.service (feature 131). Temp SQLite + patched
SessionLocal -- the same shape tests/modules/beat/test_project_service.py
uses.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.series import service as series_service
from app.modules.series.models import Series
from app.modules.story import service
from app.modules.story.models import (
    Episode,
    Story,
    StoryChapter,
    StoryCharacter,
    StoryCheckpoint,
    StoryLocation,
    StoryRun,
    StoryScene,
    StoryChannel,
)

_STORY_TABLES = [
    Series.__table__, StoryChannel.__table__, Episode.__table__, Story.__table__,
    StoryCharacter.__table__, StoryLocation.__table__, StoryChapter.__table__,
    StoryScene.__table__, StoryRun.__table__, StoryCheckpoint.__table__,
]


class _StoryServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.tmpdir.name) / 'test.db'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine, tables=_STORY_TABLES)
        self.Session = sessionmaker(bind=self.engine)
        self._patchers = [
            patch.object(service, "SessionLocal", self.Session),
            patch.object(series_service, "SessionLocal", self.Session),
        ]
        for p in self._patchers:
            p.start()

    def tearDown(self):
        for p in self._patchers:
            p.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _series(self, name="Decisive Battles") -> Series:
        return series_service.create_series(name, "")


class ChannelCrudTests(_StoryServiceTestCase):
    def test_create_get_list_update_delete(self):
        ch = service.create_channel(name="History EN", language="en", niche="ancient warfare")
        self.assertEqual(service.get_channel(ch.id).niche, "ancient warfare")
        self.assertEqual(len(service.list_channels()), 1)
        service.update_channel(ch.id, niche="medieval")
        self.assertEqual(service.get_channel(ch.id).niche, "medieval")
        service.delete_channel(ch.id)
        with self.assertRaises(NotFoundError):
            service.get_channel(ch.id)

    def test_get_missing_channel_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            service.get_channel(999)


class EpisodeTests(_StoryServiceTestCase):
    def test_orphan_series_ref_is_allowed(self):
        # series_id is a bare int (Series is another module) -- an orphan
        # is harmless, not an error worth a cross-module lookup.
        ep = service.create_episode(series_id=123, order=1)
        self.assertEqual(ep.series_id, 123)

    def test_list_episodes_ordered(self):
        s = self._series()
        service.create_episode(series_id=s.id, order=2, title="B")
        service.create_episode(series_id=s.id, order=1, title="A")
        eps = service.list_episodes_for_series(s.id)
        self.assertEqual([e.title for e in eps], ["A", "B"])


class StoryTests(_StoryServiceTestCase):
    def test_create_links_episode(self):
        s = self._series()
        ep = service.create_episode(series_id=s.id, order=1)
        st = service.create_story(
            title="Cannae 216 BC", mode="HISTORY", episode_id=ep.id, project_config_json={"render": {"profile": "SOCIAL_LANDSCAPE"}},
            story_bible_json={}, style_bible_json={}, budget_usd=2.0, production_profile="BALANCED",
            reference_notes="Polybius (my notes)", logline=None, genre="military history", content_idea_id=None,
        )
        self.assertEqual(service.get_episode(ep.id).story_id, st.id)
        # project_config_json is opaque in Phase 1 -- stored as given
        self.assertEqual(service.get_story(st.id).project_config_json, {"render": {"profile": "SOCIAL_LANDSCAPE"}})

    def test_create_with_bad_episode_raises(self):
        with self.assertRaises(NotFoundError):
            service.create_story(
                title="x", mode="STORY", episode_id=777, project_config_json={},
                story_bible_json={}, style_bible_json={}, budget_usd=None, production_profile="BALANCED",
                reference_notes=None, logline=None, genre=None, content_idea_id=None,
            )

    def test_list_stories_filters_by_mode(self):
        for mode in ("STORY", "HISTORY", "HISTORY"):
            service.create_story(
                title=f"t-{mode}", mode=mode, episode_id=None, project_config_json={},
                story_bible_json={}, style_bible_json={}, budget_usd=None, production_profile="BALANCED",
                reference_notes=None, logline=None, genre=None, content_idea_id=None,
            )
        self.assertEqual(len(service.list_stories(mode="HISTORY")), 2)
        self.assertEqual(len(service.list_stories(mode="STORY")), 1)

    def test_patch_story(self):
        st = self._new_story()
        service.patch_story(st.id, {"status": "DEVELOPING", "logline": "a general's gamble"})
        row = service.get_story(st.id)
        self.assertEqual(row.status, "DEVELOPING")
        self.assertEqual(row.logline, "a general's gamble")

    def test_delete_story_cascades_children(self):
        st = self._new_story()
        service.add_character(st.id, name="Hannibal")
        chap = service.add_chapter(st.id, order=1, title="The Trap")
        service.add_scene(chap.id, order=1, narration="He drew up his line.", dialogue_json=[],
                          character_ids_json=[], visual_mode="STILL", visual_mode_source="AUTO", duration_hint=6.0)
        service.delete_story(st.id)
        self.assertEqual(service.list_characters(st.id), [])
        self.assertEqual(service.list_chapters(st.id), [])

    def test_delete_story_blocked_by_active_run(self):
        st = self._new_story()
        with self.Session() as db:
            db.add(StoryRun(story_id=st.id, scope="STORY_PLAN", status="SCENE_BREAKDOWN"))
            db.commit()
        with self.assertRaises(ValidationError):
            service.delete_story(st.id)

    def _new_story(self) -> Story:
        return service.create_story(
            title="Cannae", mode="HISTORY", episode_id=None, project_config_json={},
            story_bible_json={}, style_bible_json={}, budget_usd=None, production_profile="BALANCED",
            reference_notes=None, logline=None, genre=None, content_idea_id=None,
        )


class ChapterSceneTests(_StoryServiceTestCase):
    def setUp(self):
        super().setUp()
        self.story = service.create_story(
            title="Cannae", mode="HISTORY", episode_id=None, project_config_json={},
            story_bible_json={}, style_bible_json={}, budget_usd=None, production_profile="BALANCED",
            reference_notes=None, logline=None, genre=None, content_idea_id=None,
        )

    def test_scenes_ordered_within_chapter(self):
        chap = service.add_chapter(self.story.id, order=1)
        service.add_scene(chap.id, order=3, dialogue_json=[], character_ids_json=[], narration="c",
                          visual_mode="STILL", visual_mode_source="AUTO", duration_hint=5.0)
        service.add_scene(chap.id, order=1, dialogue_json=[], character_ids_json=[], narration="a",
                          visual_mode="STILL", visual_mode_source="AUTO", duration_hint=5.0)
        self.assertEqual([s.narration for s in service.list_scenes(chap.id)], ["a", "c"])

    def test_add_scene_to_missing_chapter_raises(self):
        with self.assertRaises(NotFoundError):
            service.add_scene(999, order=1, dialogue_json=[], character_ids_json=[], narration="x",
                              visual_mode="STILL", visual_mode_source="AUTO", duration_hint=5.0)

    def test_update_scene_scores_persist(self):
        chap = service.add_chapter(self.story.id, order=1)
        sc = service.add_scene(chap.id, order=1, dialogue_json=[], character_ids_json=[], narration="x",
                               visual_mode="STILL", visual_mode_source="AUTO", duration_hint=5.0)
        service.update_scene(sc.id, importance_score=88, movement_score=12, composite_score=54,
                             visual_mode="STILL_WITH_MOTION", visual_mode_source="USER")
        row = service.list_scenes(chap.id)[0]
        self.assertEqual(row.importance_score, 88)
        self.assertEqual(row.visual_mode_source, "USER")


class StoryRunReadTests(_StoryServiceTestCase):
    def test_reconcile_marks_active_runs_failed(self):
        st = service.create_story(
            title="t", mode="STORY", episode_id=None, project_config_json={},
            story_bible_json={}, style_bible_json={}, budget_usd=None, production_profile="BALANCED",
            reference_notes=None, logline=None, genre=None, content_idea_id=None,
        )
        with self.Session() as db:
            db.add(StoryRun(story_id=st.id, scope="STORY_PLAN", status="SCENE_BREAKDOWN"))
            db.add(StoryRun(story_id=st.id, scope="STORY_PLAN", status="COMPLETED"))
            db.commit()
        n = service.reconcile_story_runs_on_startup()
        self.assertEqual(n, 1)
        runs = {r.status for r in service.list_runs_for_story(st.id)}
        self.assertEqual(runs, {"FAILED", "COMPLETED"})
        failed = next(r for r in service.list_runs_for_story(st.id) if r.status == "FAILED")
        self.assertEqual(failed.failed_stage, "SCENE_BREAKDOWN")
        self.assertEqual(failed.error_code, "STORY_RUN_INTERRUPTED")


if __name__ == "__main__":
    unittest.main()
