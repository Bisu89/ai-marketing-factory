"""Tests for the resumable STORY_PLAN run
(app/pipelines/story_pipeline.py orchestration + story_stages.py,
feature 132 Phase 4). The five LLM `generate_*` functions are patched with
canned output -- exactly how tests/api/test_factory_pipeline.py patches
`generate_beat_plan` etc. The deterministic stages (SCENE_CLASSIFICATION,
cost guard) run for real.
"""

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.pipelines import story_pipeline as sp
from app.pipelines import story_stages
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.ai.llm_client import AICredentials
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
)

_TABLES = [
    Episode.__table__, Story.__table__, StoryChapter.__table__, StoryScene.__table__,
    StoryCharacter.__table__, StoryLocation.__table__, StoryRun.__table__, StoryCheckpoint.__table__,
]

_DEV = {
    "premise": "A courier must cross a besieged city before dawn.",
    "synopsis": "Mara carries a sealed order through enemy lines while the walls fall.",
    "central_conflict": "Duty versus survival.",
    "tone": "tense, nocturnal",
    "setting_summary": "A medieval city under siege, one night.",
    "themes": ["duty", "fear"],
}
_BIBLE = {
    "world_rules": ["No magic.", "The siege is in its ninth day."],
    "timeline": ["Dusk: the order is given", "Midnight: the gate falls", "Dawn: Mara arrives"],
    "locations": [
        {"name": "The Low Gate", "description": "A cramped sally port", "mood": "claustrophobic"},
        {"name": "Ash Market", "description": "A burned-out square", "mood": "desolate"},
    ],
    "style": {"palette": "ash and ember", "lighting": "torch and moon", "mood": "grim", "visual_references": ["Roma night"]},
}
_CHARS = {
    "characters": [
        {"name": "Mara", "role": "courier", "age": "20s", "gender": "f", "appearance": "lean, cropped hair",
         "wardrobe": "oiled leather", "personality": "stubborn", "canonical_prompt_block": "Mara: lean woman, cropped dark hair, oiled leather cloak",
         "negative_constraints": "no armor"},
        {"name": "Captain Doss", "role": "officer", "age": "50s", "gender": "m", "appearance": "grey beard",
         "wardrobe": "dented breastplate", "personality": "weary", "canonical_prompt_block": "Doss: older man, grey beard, dented breastplate",
         "negative_constraints": "no helmet"},
    ]
}
_CHAPTERS = {
    "chapters": [
        {"title": "The Order", "summary": "Doss hands Mara the seal.", "goal": "Set the stakes", "retention_notes": "Will she take it?"},
        {"title": "The Run", "summary": "Mara sprints through the fallen gate.", "goal": "Chase peak", "retention_notes": "Cliffhanger at the wall"},
    ]
}


def _scenes_for(chapter, *, action: bool):
    if action:
        return {"scenes": [
            {"scene_type": "CLIMAX", "narration": "Mara runs as the gate shatters and soldiers charge; she leaps the rubble and sprints.",
             "dialogue": [{"character_name": "Mara", "line": "Move!"}], "character_names": ["Mara"],
             "location_name": "The Low Gate", "camera": "tracking shot", "emotion": "panic",
             "time_of_day": "night", "duration_hint": 7},
            {"scene_type": "TRANSITION", "narration": "She reaches the Ash Market and stops to breathe.",
             "dialogue": [], "character_names": ["Mara"], "location_name": "Ash Market",
             "camera": "wide", "emotion": "relief", "time_of_day": "night", "duration_hint": 5},
        ]}
    return {"scenes": [
        {"scene_type": "SETUP", "narration": "Captain Doss presses the sealed order into Mara's hand and says nothing.",
         "dialogue": [{"character_name": "Captain Doss", "line": "Before dawn. No one else."}],
         "character_names": ["Mara", "Captain Doss"], "location_name": "The Low Gate",
         "camera": "close", "emotion": "dread", "time_of_day": "dusk", "duration_hint": 6},
    ]}


class _SyncThread:
    """Runs the target inline on .start() -- so retry_run / create_and_start_run
    (which spawn a real daemon thread in production) are deterministic here.
    """

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        if self._target is not None:
            self._target(*self._args, **self._kwargs)


class _RunTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine, tables=_TABLES)
        self.Session = sessionmaker(bind=self.engine)
        self._patchers = [
            patch("app.modules.story.service.SessionLocal", self.Session),
            patch.object(sp.threading, "Thread", _SyncThread),
            patch.object(story_stages, "resolve_ai_credentials", return_value=AICredentials("anthropic", "test-key")),
            patch.object(story_stages, "generate_story_development", return_value=_DEV),
            patch.object(story_stages, "generate_story_bible", return_value=_BIBLE),
            patch.object(story_stages, "generate_character_bible", return_value=_CHARS),
            patch.object(story_stages, "generate_chapter_outline", return_value=_CHAPTERS),
        ]
        for p in self._patchers:
            p.start()
        self.settings = get_settings()

    def tearDown(self):
        for p in self._patchers:
            p.stop()
        self.engine.dispose()

    def _story(self, *, config=None, budget=None) -> int:
        st = service.create_story(
            title="The Courier", mode="STORY", episode_id=None, project_config_json=config or {},
            story_bible_json={}, style_bible_json={}, budget_usd=budget, production_profile="BALANCED",
            reference_notes=None, logline="A courier races the dawn.", genre="thriller", content_idea_id=None,
        )
        return st.id

    def _breakdown_side_effect(self):
        def _fn(credentials, story, chapter, characters, locations, n_chapters=1):
            return _scenes_for(chapter, action=(chapter.order == 2))
        return _fn


class HappyPathTests(_RunTestCase):
    def test_full_plan_run_reaches_ready(self):
        sid = self._story(config={"scene_classification": {"ai_video_max_ratio": 0.5}})
        run, created = service.create_run(sid)
        self.assertTrue(created)
        with patch.object(story_stages, "generate_scene_breakdown", side_effect=self._breakdown_side_effect()):
            sp._execute_story_plan_sync(run.id, sid, self.settings)

        done = service.get_run(run.id)
        self.assertEqual(done.status, "READY")
        self.assertIsNone(done.failed_stage)
        self.assertIsNotNone(done.est_cost_json)

        # every stage checkpoint COMPLETED
        cps = {c.stage: c.status for c in service.get_checkpoints(run.id)}
        self.assertEqual(
            set(cps),
            {"STORY_DEVELOPMENT", "STORY_BIBLE", "CHARACTER_BIBLE", "CHAPTER_OUTLINE", "SCENE_BREAKDOWN", "SCENE_CLASSIFICATION"},
        )
        self.assertTrue(all(s == "COMPLETED" for s in cps.values()))

        # real rows created
        self.assertEqual(len(service.list_characters(sid)), 2)
        self.assertEqual(len(service.list_locations(sid)), 2)
        chapters = service.list_chapters(sid)
        self.assertEqual([c.order for c in chapters], [1, 2])
        ch2_scenes = service.list_scenes(chapters[1].id)
        self.assertEqual(ch2_scenes[0].scene_type, "CLIMAX")
        # dialogue + character ids resolved to real rows
        self.assertEqual(len(ch2_scenes[0].character_ids_json), 1)
        # scene director ran -> the battle scene is AI_VIDEO, scores persisted
        self.assertEqual(ch2_scenes[0].visual_mode, "AI_VIDEO")
        self.assertIsNotNone(ch2_scenes[0].composite_score)
        # story status advanced
        self.assertEqual(service.get_story(sid).status, "SCENES_READY")

    def test_rerun_is_idempotent_no_duplicate_rows(self):
        sid = self._story()
        run, _ = service.create_run(sid)
        with patch.object(story_stages, "generate_scene_breakdown", side_effect=self._breakdown_side_effect()) as gen:
            sp._execute_story_plan_sync(run.id, sid, self.settings)
            calls_first = gen.call_count
            # simulate a retry: mark FAILED, then retry_run replays
            service.set_run_fields(run.id, status="FAILED", failed_stage="SCENE_BREAKDOWN")
            sp.retry_run(run.id, self.settings)

        self.assertEqual(len(service.list_chapters(sid)), 2)      # not 4
        self.assertEqual(len(service.list_characters(sid)), 2)    # not 4
        self.assertEqual(gen.call_count, calls_first)             # breakdown skipped on replay


class CostGuardTests(_RunTestCase):
    def test_block_pauses_at_needs_review(self):
        sid = self._story(config={"cost_guard": {"max_total_usd": 0.0001, "block_on_exceed": True}})
        run, _ = service.create_run(sid)
        with patch.object(story_stages, "generate_scene_breakdown", side_effect=self._breakdown_side_effect()):
            sp._execute_story_plan_sync(run.id, sid, self.settings)

        done = service.get_run(run.id)
        self.assertEqual(done.status, "NEEDS_REVIEW")
        self.assertEqual(done.failed_stage, "SCENE_CLASSIFICATION")
        self.assertEqual(done.error_code, "COST_GUARD_BLOCKED")
        self.assertTrue(done.requires_human_review)
        # the SCENE_BREAKDOWN work still landed
        self.assertEqual(len(service.list_chapters(sid)), 2)

    def test_retry_after_raising_cap_reaches_ready(self):
        sid = self._story(config={"cost_guard": {"max_total_usd": 0.0001}, "scene_classification": {"ai_video_max_ratio": 0.5}})
        run, _ = service.create_run(sid)
        with patch.object(story_stages, "generate_scene_breakdown", side_effect=self._breakdown_side_effect()):
            sp._execute_story_plan_sync(run.id, sid, self.settings)
            self.assertEqual(service.get_run(run.id).status, "NEEDS_REVIEW")
            service.patch_story(sid, {"project_config_json": {"cost_guard": {"max_total_usd": 100.0}}})
            sp.retry_run(run.id, self.settings)

        self.assertEqual(service.get_run(run.id).status, "READY")
        self.assertEqual(service.get_run(run.id).attempt, 2)


class FailureAndControlTests(_RunTestCase):
    def test_ai_not_configured_fails_first_stage(self):
        sid = self._story()
        run, _ = service.create_run(sid)
        with patch.object(story_stages, "resolve_ai_credentials", return_value=None):
            sp._execute_story_plan_sync(run.id, sid, self.settings)
        done = service.get_run(run.id)
        self.assertEqual(done.status, "FAILED")
        self.assertEqual(done.failed_stage, "STORY_DEVELOPMENT")
        self.assertEqual(done.error_code, "AI_NOT_CONFIGURED")
        cp = next(c for c in service.get_checkpoints(run.id) if c.stage == "STORY_DEVELOPMENT")
        self.assertEqual(cp.status, "FAILED")

    def test_cancel_stops_at_next_boundary(self):
        sid = self._story()
        run, _ = service.create_run(sid)

        real_bible = story_stages.generate_story_bible

        def _cancel_then_run(*a, **kw):
            sp._cancel_event_for(run.id).set()
            return _BIBLE

        with patch.object(story_stages, "generate_story_bible", side_effect=_cancel_then_run):
            sp._execute_story_plan_sync(run.id, sid, self.settings)

        done = service.get_run(run.id)
        self.assertEqual(done.status, "CANCELLED")
        # STORY_DEVELOPMENT completed, nothing past STORY_BIBLE
        self.assertEqual(len(service.list_chapters(sid)), 0)

    def test_retry_rejects_a_running_run(self):
        sid = self._story()
        run, _ = service.create_run(sid)
        service.set_run_fields(run.id, status="CHAPTER_OUTLINE")
        with self.assertRaises(ValidationError):
            sp.retry_run(run.id, self.settings)

    def test_reconcile_marks_interrupted_run_and_checkpoint_failed(self):
        sid = self._story()
        run, _ = service.create_run(sid)
        service.set_run_fields(run.id, status="CHARACTER_BIBLE")
        service.start_checkpoint(run.id, "CHARACTER_BIBLE")   # RUNNING
        n = service.reconcile_story_runs_on_startup()
        self.assertEqual(n, 1)
        done = service.get_run(run.id)
        self.assertEqual(done.status, "FAILED")
        self.assertEqual(done.failed_stage, "CHARACTER_BIBLE")
        cp = next(c for c in service.get_checkpoints(run.id) if c.stage == "CHARACTER_BIBLE")
        self.assertEqual(cp.status, "FAILED")

    def test_second_start_reuses_the_active_run(self):
        sid = self._story()
        run1, created1 = service.create_run(sid)
        service.set_run_fields(run1.id, status="STORY_BIBLE")
        run2, created2 = service.create_run(sid)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(run1.id, run2.id)


if __name__ == "__main__":
    unittest.main()
