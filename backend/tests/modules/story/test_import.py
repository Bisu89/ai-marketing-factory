"""Tests for service.import_story_package (feature 136) -- the "paste a
story written elsewhere" path that skips the AI planning pipeline.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.story import service
from app.modules.story.models import Episode, Story, StoryChapter, StoryCharacter, StoryLocation, StoryScene
from app.modules.story.schemas import StoryImportIn

_TABLES = [
    Episode.__table__, Story.__table__, StoryChapter.__table__, StoryScene.__table__,
    StoryCharacter.__table__, StoryLocation.__table__,
]

_PKG = {
    "story_bible": {"premise": "A courier races the dawn.", "themes": ["duty"]},
    "style_bible": {"palette": "ash and ember", "mood": "grim"},
    "characters": [
        {"name": "Mara", "role": "courier", "canonical_prompt_block": "Mara: lean woman, cropped hair"},
        {"name": "Doss", "role": "captain"},
    ],
    "locations": [{"name": "The Low Gate", "description": "a cramped sally port", "mood": "claustrophobic"}],
    "chapters": [
        {
            "title": "The Order",
            "goal": "set the stakes",
            "scenes": [
                {
                    "scene_type": "SETUP", "narration": "Doss presses the seal into Mara's hand.",
                    "dialogue": [{"character_name": "Doss", "line": "Before dawn."}],
                    "character_names": ["Mara", "Doss"], "location_name": "The Low Gate",
                    "camera": "close", "emotion": "dread", "duration_hint": 6,
                },
                {
                    "scene_type": "CLIMAX", "narration": "Mara runs as the gate shatters.",
                    "character_names": ["Mara"], "location_name": "The Low Gate",
                    "camera": "tracking shot", "emotion": "panic", "duration_hint": 40,
                },
            ],
        }
    ],
}


class _ImportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.tmpdir.name) / 'test.db'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine, tables=_TABLES)
        self.Session = sessionmaker(bind=self.engine)
        self.p = patch("app.modules.story.service.SessionLocal", self.Session)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _story(self) -> int:
        return service.create_story(
            title="The Courier", mode="STORY", episode_id=None, project_config_json={},
            story_bible_json={}, style_bible_json={}, budget_usd=None, production_profile="BALANCED",
            reference_notes=None, logline=None, genre=None, content_idea_id=None,
        ).id

    def _pkg(self, **over) -> dict:
        return StoryImportIn.model_validate({**_PKG, **over}).model_dump()


class ImportTests(_ImportTestCase):
    def test_import_materialises_every_row_and_sets_status(self):
        sid = self._story()
        result = service.import_story_package(sid, self._pkg())

        self.assertEqual(result["characters"], 2)
        self.assertEqual(result["locations"], 1)
        self.assertEqual(result["chapters"], 1)
        self.assertEqual(result["scenes"], 2)
        self.assertEqual(service.get_story(sid).status, "SCENES_READY")
        self.assertEqual(service.get_story(sid).story_bible_json["premise"], "A courier races the dawn.")
        self.assertEqual(service.get_story(sid).style_bible_json["palette"], "ash and ember")

        chapter = service.list_chapters(sid)[0]
        scenes = service.list_scenes(chapter.id)
        self.assertEqual([s.order for s in scenes], [1, 2])
        # names resolved to real ids
        char_ids = {c.name: c.id for c in service.list_characters(sid)}
        self.assertEqual(sorted(scenes[0].character_ids_json), sorted([char_ids["Mara"], char_ids["Doss"]]))
        self.assertEqual(scenes[0].dialogue_json, [{"character_id": char_ids["Doss"], "line": "Before dawn."}])
        self.assertEqual(scenes[0].location_id, service.list_locations(sid)[0].id)
        # duration clamped (40 -> 20)
        self.assertEqual(scenes[1].duration_hint, 20.0)
        # unknown scene types would fall back, CLIMAX is valid
        self.assertEqual(scenes[1].scene_type, "CLIMAX")

    def test_unknown_scene_type_falls_back_to_body(self):
        sid = self._story()
        pkg = self._pkg()
        pkg["chapters"][0]["scenes"][0]["scene_type"] = "MONTAGE"
        result = service.import_story_package(sid, pkg)
        scenes = service.list_scenes(service.list_chapters(sid)[0].id)
        self.assertEqual(scenes[0].scene_type, "BODY")
        self.assertEqual(result["scenes"], 2)

    def test_unresolved_character_name_is_reported_not_fatal(self):
        sid = self._story()
        pkg = self._pkg()
        pkg["chapters"][0]["scenes"][0]["character_names"] = ["Mara", "Ghost"]
        result = service.import_story_package(sid, pkg)
        self.assertIn("ghost", result["unresolved_character_names"])
        scenes = service.list_scenes(service.list_chapters(sid)[0].id)
        self.assertEqual(len(scenes[0].character_ids_json), 1)  # only Mara

    def test_second_import_needs_replace(self):
        sid = self._story()
        service.import_story_package(sid, self._pkg())
        with self.assertRaises(ValidationError):
            service.import_story_package(sid, self._pkg())

        service.import_story_package(sid, self._pkg(), replace=True)
        self.assertEqual(len(service.list_chapters(sid)), 1)  # not 2
        self.assertEqual(len(service.list_characters(sid)), 2)  # not 4

    def test_missing_story_raises(self):
        with self.assertRaises(NotFoundError):
            service.import_story_package(999, self._pkg())

    def test_schema_rejects_a_chapter_with_no_scenes(self):
        with self.assertRaises(Exception):
            StoryImportIn.model_validate({"chapters": [{"title": "Empty", "scenes": []}]})


if __name__ == "__main__":
    unittest.main()
