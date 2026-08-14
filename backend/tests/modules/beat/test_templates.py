"""Tests for Task 12 (Project Templates + One-Click Presets -- see
docs/features/39-project-templates.md): template validation, template ->
project config application, built-in template immutability/isolation,
version persistence, and custom-template save/sanitization.
"""

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ValidationError
from app.modules.beat.schemas import (
    BUILTIN_TEMPLATES,
    COUPLE_STORY_TEMPLATE,
    CUSTOM_TEMPLATE,
    DEFAULT_PROJECT_CONFIG,
    EMOTIONAL_STORY_TEMPLATE,
    AudioProjectConfig,
    Beat,
    BeatMotionPreset,
    BeatPlan,
    BeatType,
    CaptionsProjectConfig,
    MotionProjectConfig,
    ProjectConfig,
    RenderProjectConfig,
    Template,
    effective_motion_preset,
    sanitize_project_config_for_template,
)
from app.modules.beat.service import (
    delete_custom_template,
    load_custom_templates,
    save_custom_template,
)


class TemplateValidationTests(unittest.TestCase):
    def test_valid_template_is_accepted(self):
        template = Template(id="my_template", name="My Template", config=ProjectConfig())
        self.assertEqual(template.version, 1)
        self.assertFalse(template.builtin)

    def test_invalid_motion_preset_rejected(self):
        with self.assertRaises(PydanticValidationError):
            MotionProjectConfig(default_preset="NOT_A_REAL_PRESET")

    def test_invalid_caption_preset_rejected(self):
        with self.assertRaises(PydanticValidationError):
            CaptionsProjectConfig(preset="not_a_real_preset")

    def test_invalid_music_volume_rejected(self):
        with self.assertRaises(PydanticValidationError):
            AudioProjectConfig(music_volume=5.0)
        with self.assertRaises(PydanticValidationError):
            AudioProjectConfig(music_volume=-1.0)

    def test_invalid_render_profile_rejected(self):
        with self.assertRaises(PydanticValidationError):
            RenderProjectConfig(profile="NOT_A_REAL_PROFILE")

    def test_blank_template_name_rejected(self):
        with self.assertRaises(PydanticValidationError):
            Template(id="x", name="   ", config=ProjectConfig())

    def test_unknown_field_rejected(self):
        with self.assertRaises(PydanticValidationError):
            ProjectConfig.model_validate({"render": {}, "unexpected_field": True})


class BuiltinTemplateTests(unittest.TestCase):
    def test_three_builtin_templates_exist(self):
        ids = {t.id for t in BUILTIN_TEMPLATES}
        self.assertEqual(ids, {"emotional_story", "couple_story", "custom"})
        self.assertTrue(all(t.builtin for t in BUILTIN_TEMPLATES))

    def test_emotional_story_defaults(self):
        config = EMOTIONAL_STORY_TEMPLATE.config
        self.assertEqual(config.render.profile, "SOCIAL_VERTICAL")
        self.assertEqual(config.motion.default_preset, BeatMotionPreset.SLOW_PUSH_IN)
        self.assertTrue(config.captions.enabled)
        self.assertTrue(config.audio.narration_enabled)
        self.assertTrue(config.audio.music_enabled)

    def test_couple_story_uses_subtle_motion_and_emotional_captions(self):
        config = COUPLE_STORY_TEMPLATE.config
        self.assertEqual(config.motion.default_preset, BeatMotionPreset.SLOW_PUSH_IN)
        self.assertEqual(config.captions.preset, "emotional")

    def test_custom_template_uses_plain_system_defaults(self):
        self.assertEqual(CUSTOM_TEMPLATE.config.motion, ProjectConfig().motion)
        self.assertEqual(CUSTOM_TEMPLATE.config.captions.preset, ProjectConfig().captions.preset)

    def test_no_builtin_template_carries_asset_beat_or_job_ids(self):
        # ProjectConfig's schema has no such fields at all -- this test
        # guards against a future field addition accidentally introducing
        # one (Task 12 section 5's explicit "do NOT put asset/project/beat/
        # render job IDs inside the built-in template").
        for template in BUILTIN_TEMPLATES:
            dumped = template.config.model_dump()
            for forbidden in ("asset_id", "project_id", "beat_id", "render_job_id", "job_id"):
                self.assertNotIn(forbidden, json.dumps(dumped))


class TemplateApplicationTests(unittest.TestCase):
    """Template -> new project: BeatPlan.config becomes a snapshot of the
    chosen template's config (see VideoFactoryPage.tsx's "Use Template").
    """

    def test_applying_a_template_produces_expected_project_config(self):
        plan = BeatPlan(
            beats=[Beat(id="b1", order=1, duration=2.0, type=BeatType.HOOK)],
            config=EMOTIONAL_STORY_TEMPLATE.config.model_copy(deep=True),
        )
        self.assertEqual(plan.config.motion.default_preset, BeatMotionPreset.SLOW_PUSH_IN)
        self.assertEqual(plan.config.template_id, "emotional_story")
        self.assertEqual(plan.config.template_version, 1)

    def test_beat_override_beats_project_default_beats_system_default(self):
        config = EMOTIONAL_STORY_TEMPLATE.config  # default_preset = SLOW_PUSH_IN
        beat_with_override = Beat(id="b1", order=1, duration=2.0, type=BeatType.HOOK, motion_preset=BeatMotionPreset.PAN_RIGHT)
        beat_without_override = Beat(id="b2", order=2, duration=2.0, type=BeatType.BODY)

        self.assertEqual(effective_motion_preset(beat_with_override, config), BeatMotionPreset.PAN_RIGHT)
        self.assertEqual(effective_motion_preset(beat_without_override, config), BeatMotionPreset.SLOW_PUSH_IN)
        # No template at all (system default) -- DEFAULT_PROJECT_CONFIG.
        self.assertEqual(effective_motion_preset(beat_without_override, DEFAULT_PROJECT_CONFIG), BeatMotionPreset.STATIC)


class TemplateIsolationTests(unittest.TestCase):
    """Critical test (Task 12 section 30): mutating a project must never
    mutate the built-in template it came from.
    """

    def test_mutating_project_config_does_not_mutate_builtin_template(self):
        original_preset = EMOTIONAL_STORY_TEMPLATE.config.motion.default_preset
        project_config = EMOTIONAL_STORY_TEMPLATE.config.model_copy(deep=True)

        project_config.motion.default_preset = BeatMotionPreset.PAN_LEFT
        project_config.captions.preset = "quote"
        project_config.audio.music_volume = 0.9

        self.assertEqual(EMOTIONAL_STORY_TEMPLATE.config.motion.default_preset, original_preset)
        self.assertEqual(EMOTIONAL_STORY_TEMPLATE.config.captions.preset, "big_statement")
        self.assertEqual(EMOTIONAL_STORY_TEMPLATE.config.audio.music_volume, 0.18)

    def test_two_projects_from_the_same_template_are_independent(self):
        project_a = EMOTIONAL_STORY_TEMPLATE.config.model_copy(deep=True)
        project_b = EMOTIONAL_STORY_TEMPLATE.config.model_copy(deep=True)

        project_a.motion.default_preset = BeatMotionPreset.PAN_RIGHT

        self.assertEqual(project_b.motion.default_preset, BeatMotionPreset.SLOW_PUSH_IN)


class TemplateVersionTests(unittest.TestCase):
    def test_builtin_template_version_is_persisted_through_serialization(self):
        raw = json.loads(EMOTIONAL_STORY_TEMPLATE.model_dump_json())
        self.assertEqual(raw["version"], 1)

    def test_project_config_carries_template_version_snapshot(self):
        plan = BeatPlan(
            beats=[Beat(id="b1", order=1, duration=2.0, type=BeatType.HOOK)],
            config=COUPLE_STORY_TEMPLATE.config.model_copy(deep=True),
        )
        self.assertEqual(plan.config.template_version, 1)


class CustomTemplatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "templates.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_and_load_round_trips(self):
        template = Template(id="colombia_v2", name="Colombia Emotional V2", config=ProjectConfig())
        save_custom_template(template, self.path)

        loaded = load_custom_templates(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, "colombia_v2")
        self.assertFalse(loaded[0].builtin)

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(load_custom_templates(self.path), [])

    def test_cannot_save_a_template_reusing_a_builtin_id(self):
        template = Template(id="emotional_story", name="Shadow attempt", config=ProjectConfig())
        with self.assertRaises(ValidationError):
            save_custom_template(template, self.path)

    def test_delete_removes_only_the_named_template(self):
        save_custom_template(Template(id="a", name="A", config=ProjectConfig()), self.path)
        save_custom_template(Template(id="b", name="B", config=ProjectConfig()), self.path)

        remaining = delete_custom_template("a", self.path)
        self.assertEqual([t.id for t in remaining], ["b"])

    def test_cannot_delete_a_builtin_template(self):
        with self.assertRaises(ValidationError):
            delete_custom_template("custom", self.path)

    def test_saving_twice_with_same_id_replaces_not_duplicates(self):
        save_custom_template(Template(id="a", name="A v1", config=ProjectConfig()), self.path)
        save_custom_template(Template(id="a", name="A v2", config=ProjectConfig()), self.path)

        loaded = load_custom_templates(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "A v2")


class SaveProjectAsTemplateTests(unittest.TestCase):
    """Project config -> sanitize -> Template config (Task 12 section 23)."""

    def test_sanitize_strips_template_provenance(self):
        project_config = EMOTIONAL_STORY_TEMPLATE.config.model_copy(deep=True)
        self.assertIsNotNone(project_config.template_id)

        sanitized = sanitize_project_config_for_template(project_config)
        self.assertIsNone(sanitized.template_id)
        self.assertIsNone(sanitized.template_version)
        # Everything else (the actual render/motion/caption/audio settings
        # a user would want to reuse) survives untouched.
        self.assertEqual(sanitized.motion.default_preset, project_config.motion.default_preset)
        self.assertEqual(sanitized.captions.preset, project_config.captions.preset)

    def test_project_config_never_contains_project_specific_identifiers(self):
        # ProjectConfig's own schema has no asset_id/beat_id/job_id/output_path
        # fields at all -- confirms "sanitize" needs to strip nothing beyond
        # template provenance, by construction, not by a strip-list that
        # could miss something.
        fields = set(ProjectConfig.model_fields.keys())
        # Task 18 added `factory` (see docs/features/44-one-click-factory-pipeline.md)
        # -- plain booleans only, no asset_id/beat_id/job_id/output_path, so
        # this invariant still holds with it included.
        self.assertEqual(fields, {"render", "motion", "captions", "audio", "factory", "template_id", "template_version"})


class BackwardCompatibilityTests(unittest.TestCase):
    def test_beat_plan_without_config_key_loads_with_system_defaults(self):
        old_style_plan = {
            "beats": [{"id": "beat_01", "order": 1, "duration": 4.0, "type": "HOOK"}],
        }
        plan = BeatPlan.model_validate(old_style_plan)
        self.assertEqual(plan.config.motion.default_preset, BeatMotionPreset.STATIC)
        self.assertTrue(plan.config.audio.narration_enabled)
        self.assertIsNone(plan.config.template_id)

    def test_beat_plan_without_project_name_loads_fine(self):
        old_style_plan = {
            "beats": [{"id": "beat_01", "order": 1, "duration": 4.0, "type": "HOOK"}],
        }
        plan = BeatPlan.model_validate(old_style_plan)
        self.assertIsNone(plan.project_name)


if __name__ == "__main__":
    unittest.main()
