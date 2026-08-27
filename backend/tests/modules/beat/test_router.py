"""Tests for the Beat persistence router (app/modules/beat/router.py):
GET/PUT /beat-plan against a real beats.json on disk under a temp
library_dir. Route handlers are called directly as plain functions --
matching this codebase's established test convention (see e.g.
tests/api/test_composition_render.py calling render_composition() directly)
-- no TestClient/HTTP layer anywhere in this test suite.
"""

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.exceptions import ValidationError as AppValidationError
from app.modules.beat.router import (
    CreateTemplateRequest,
    UpdateTemplateRequest,
    create_template,
    delete_template,
    get_beat_plan,
    list_templates,
    put_beat_plan,
    update_template,
)
from app.modules.beat.schemas import Beat, BeatPlan, BeatType, ProjectConfig


def _make_plan() -> BeatPlan:
    return BeatPlan(
        script_text="A short vertical-video script.",
        beats=[
            Beat(id="beat_01", order=1, duration=4.0, type=BeatType.HOOK, narration="Meet Anna.", visual_hint="a"),
            Beat(id="beat_02", order=2, duration=5.0, type=BeatType.BODY, narration="Her story.", visual_hint="b"),
        ],
    )


class BeatPlanRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.settings = Settings(library_dir=self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_before_any_save_returns_none(self):
        self.assertIsNone(get_beat_plan(self.settings))

    def test_put_then_get_round_trips_the_same_plan(self):
        plan = _make_plan()
        saved = put_beat_plan(plan, self.settings)
        self.assertEqual(saved, plan)

        loaded = get_beat_plan(self.settings)
        self.assertEqual(loaded, plan)
        self.assertEqual(loaded.total_duration, 9.0)

    def test_put_writes_beats_json_under_a_library_dir_subfolder(self):
        put_beat_plan(_make_plan(), self.settings)
        expected_path = Path(self.tmpdir.name) / "_beat" / "beats.json"
        self.assertTrue(expected_path.exists())
        on_disk = json.loads(expected_path.read_text(encoding="utf-8"))
        self.assertEqual(len(on_disk["beats"]), 2)

    def test_put_with_invalid_beat_plan_is_rejected_before_reaching_the_router(self):
        # FastAPI validates the request body against BeatPlan itself before
        # calling put_beat_plan -- exercised here the same way the request
        # layer would: constructing the model is what raises.
        with self.assertRaises(PydanticValidationError):
            BeatPlan.model_validate({"beats": []})

    def test_second_put_overwrites_the_first(self):
        put_beat_plan(_make_plan(), self.settings)
        second = BeatPlan(beats=[Beat(id="only", order=1, duration=2.0, type=BeatType.ENDING)])
        put_beat_plan(second, self.settings)

        loaded = get_beat_plan(self.settings)
        self.assertEqual(len(loaded.beats), 1)
        self.assertEqual(loaded.beats[0].id, "only")

    def test_get_with_malformed_json_on_disk_raises_a_clean_validation_error(self):
        beats_json_path = Path(self.tmpdir.name) / "_beat" / "beats.json"
        beats_json_path.parent.mkdir(parents=True, exist_ok=True)
        beats_json_path.write_text("{not valid json", encoding="utf-8")

        with self.assertRaises(AppValidationError):
            get_beat_plan(self.settings)


class TemplateRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.settings = Settings(library_dir=self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_list_templates_returns_the_builtins_before_any_custom_one(self):
        templates = list_templates(self.settings)
        self.assertEqual(
            [t.id for t in templates], ["emotional_story", "couple_story", "horror", "custom"]
        )
        self.assertTrue(all(t.builtin for t in templates))

    def test_create_then_list_includes_the_new_custom_template(self):
        created = create_template(
            CreateTemplateRequest(name="Colombia Emotional V2", description="desc", config=ProjectConfig()),
            self.settings,
        )
        self.assertEqual(created.id, "colombia_emotional_v2")
        self.assertFalse(created.builtin)

        templates = list_templates(self.settings)
        self.assertEqual(len(templates), 5)
        self.assertIn("colombia_emotional_v2", [t.id for t in templates])

    def test_create_with_duplicate_name_gets_a_unique_id(self):
        first = create_template(CreateTemplateRequest(name="My Style", config=ProjectConfig()), self.settings)
        second = create_template(CreateTemplateRequest(name="My Style", config=ProjectConfig()), self.settings)
        self.assertNotEqual(first.id, second.id)

    def test_create_with_blank_name_is_rejected(self):
        with self.assertRaises(AppValidationError):
            create_template(CreateTemplateRequest(name="   ", config=ProjectConfig()), self.settings)

    def test_delete_removes_a_custom_template(self):
        created = create_template(CreateTemplateRequest(name="Temp", config=ProjectConfig()), self.settings)
        delete_template(created.id, self.settings)
        self.assertNotIn(created.id, [t.id for t in list_templates(self.settings)])

    def test_delete_nonexistent_template_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            delete_template("does_not_exist", self.settings)

    def test_delete_builtin_template_is_rejected(self):
        with self.assertRaises(AppValidationError):
            delete_template("custom", self.settings)

    def test_update_changes_name_description_and_config_and_bumps_version(self):
        created = create_template(CreateTemplateRequest(name="Original", config=ProjectConfig()), self.settings)
        self.assertEqual(created.version, 1)

        new_config = ProjectConfig()
        new_config.visual_generation.image_style_prompt = "watercolor illustration"
        updated = update_template(
            created.id,
            UpdateTemplateRequest(name="Renamed", description="new desc", config=new_config),
            self.settings,
        )

        self.assertEqual(updated.id, created.id)
        self.assertEqual(updated.name, "Renamed")
        self.assertEqual(updated.description, "new desc")
        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.config.visual_generation.image_style_prompt, "watercolor illustration")

        templates = list_templates(self.settings)
        self.assertEqual(len(templates), 5)
        reloaded = next(t for t in templates if t.id == created.id)
        self.assertEqual(reloaded.name, "Renamed")

    def test_update_nonexistent_template_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            update_template(
                "does_not_exist", UpdateTemplateRequest(name="X", config=ProjectConfig()), self.settings
            )

    def test_update_builtin_template_is_rejected(self):
        with self.assertRaises(AppValidationError):
            update_template("custom", UpdateTemplateRequest(name="X", config=ProjectConfig()), self.settings)

    def test_update_with_blank_name_is_rejected(self):
        created = create_template(CreateTemplateRequest(name="Original", config=ProjectConfig()), self.settings)
        with self.assertRaises(AppValidationError):
            update_template(created.id, UpdateTemplateRequest(name="   ", config=ProjectConfig()), self.settings)


if __name__ == "__main__":
    unittest.main()
