"""Tests for the Story -> Project compile + Factory handoff
(app/api/v1/endpoints/story_compile.py, feature 135). The Factory run
itself is patched -- this codebase's convention for a composition root
that delegates to another one (see tests/api/test_story_run_pipeline.py).
"""

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import story_compile as sc
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.beat.models import Project
from app.modules.factory.models import FactoryRun
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
    Project.__table__, FactoryRun.__table__,
]


class _SyncThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._t, self._a, self._k = target, args, kwargs or {}

    def start(self):
        if self._t:
            self._t(*self._a, **self._k)


class _CompileTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine, tables=_TABLES)
        self.Session = sessionmaker(bind=self.engine)
        self.started_projects: list[int] = []
        self._patchers = [
            patch("app.modules.story.service.SessionLocal", self.Session),
            patch("app.api.v1.endpoints.story_compile.SessionLocal", self.Session),
            patch("app.modules.beat.project_service.SessionLocal", self.Session),
            patch("app.modules.factory.service.SessionLocal", self.Session),
            patch.object(sc.threading, "Thread", _SyncThread),
            patch.object(sc, "start_factory_run", side_effect=lambda pid, *_a, **_k: self.started_projects.append(pid)),
        ]
        for p in self._patchers:
            p.start()
        self.settings = get_settings()

    def tearDown(self):
        for p in self._patchers:
            p.stop()
        self.engine.dispose()

    def _story(self, *, config=None, episode_id=None) -> int:
        st = service.create_story(
            title="The Courier", mode="STORY", episode_id=episode_id, project_config_json=config or {},
            story_bible_json={}, style_bible_json={"palette": "ash", "lighting": "torchlight", "mood": "grim"},
            budget_usd=None, production_profile="BALANCED", reference_notes=None, logline=None,
            genre=None, content_idea_id=None,
        )
        return st.id

    def _populate(self, story_id: int, *, chapters=2, scenes_per=2):
        char = service.bulk_add_characters(story_id, [
            {"name": "Mara", "canonical_prompt_block": "Mara: lean woman, cropped hair, oiled leather"},
        ])[0]
        loc = service.add_location(story_id, name="The Gate", description="a cramped sally port")
        for ci in range(1, chapters + 1):
            chap = service.add_chapter(story_id, order=ci, title=f"Chapter {ci}")
            for si in range(1, scenes_per + 1):
                service.add_scene(
                    chap.id, order=si, scene_type="BUILD",
                    narration=f"Chapter {ci} scene {si}: Mara moves through the dark.",
                    dialogue_json=[], character_ids_json=[char.id], location_id=loc.id,
                    visual_mode="STILL_WITH_MOTION", visual_mode_source="AUTO",
                    motion_preset="SLOW_PUSH_IN", camera="handheld", emotion="dread", duration_hint=6.0,
                )


class CompileTests(_CompileTestCase):
    def test_per_chapter_creates_one_project_each(self):
        sid = self._story()
        self._populate(sid, chapters=3, scenes_per=2)
        result = sc.compile_story(sid)

        self.assertEqual(result.compile_mode, "per_chapter")
        self.assertEqual(len(result.projects), 3)
        for cp in result.projects:
            self.assertFalse(cp.reused)
            self.assertEqual(cp.beat_count, 2)
        # chapter rows link back
        for chapter in service.list_chapters(sid):
            self.assertIsNotNone(chapter.compiled_project_id)

        # the plan is a valid, renderable BeatPlan with the character block baked in
        with self.Session() as db:
            proj = db.get(Project, result.projects[0].project_id)
        beats = proj.beat_plan_json["beats"]
        self.assertEqual([b["order"] for b in beats], [1, 2])
        self.assertIn("Mara: lean woman", beats[0]["visual_description"])
        self.assertEqual(proj.beat_plan_json["config"]["visual_generation"]["mode"], "ai_generated")
        self.assertTrue(proj.beat_plan_json["config"]["audio"]["narration_enabled"])
        self.assertEqual(proj.beat_plan_json["config"]["voice"]["provider"], "edge_tts")
        # BGM auto-select + image tone follow the bible/style, not a generic default
        self.assertEqual(proj.beat_plan_json["config"]["content"]["tone"], "grim")
        self.assertIn("ash", proj.beat_plan_json["config"]["visual_generation"]["image_style_prompt"])
        self.assertTrue(proj.beat_plan_json["script_locked"])

    def test_per_chapter_is_idempotent(self):
        sid = self._story()
        self._populate(sid, chapters=2, scenes_per=2)
        first = sc.compile_story(sid)
        second = sc.compile_story(sid)
        self.assertEqual(
            [p.project_id for p in first.projects], [p.project_id for p in second.projects]
        )
        self.assertTrue(all(p.reused for p in second.projects))
        with self.Session() as db:
            self.assertEqual(db.query(Project).count(), 2)  # not 4

    def test_single_mode_one_project_for_the_whole_story(self):
        sid = self._story(config={"story_compile": {"compile_mode": "single"}})
        self._populate(sid, chapters=3, scenes_per=2)
        result = sc.compile_story(sid)
        self.assertEqual(result.compile_mode, "single")
        self.assertEqual(len(result.projects), 1)
        self.assertEqual(result.projects[0].beat_count, 6)

    def test_merge_short_scenes_folds_backward(self):
        sid = self._story(config={"story_compile": {"merge_scenes_under_seconds": 3.0}})
        char = service.bulk_add_characters(sid, [{"name": "X"}])[0]
        chap = service.add_chapter(sid, order=1)
        for order, dur in ((1, 6.0), (2, 6.0), (3, 1.5)):
            service.add_scene(chap.id, order=order, scene_type="BODY", narration=f"Scene {order}.",
                              dialogue_json=[], character_ids_json=[char.id], visual_mode="STILL",
                              visual_mode_source="AUTO", duration_hint=dur)
        result = sc.compile_story(sid)
        self.assertEqual(result.projects[0].beat_count, 2)  # the 1.5s scene folds into scene 2

    def test_no_scenes_raises(self):
        sid = self._story()
        service.add_chapter(sid, order=1)
        with self.assertRaises(ValidationError):
            sc.compile_story(sid)


class ProduceTests(_CompileTestCase):
    def test_produce_compiles_then_starts_a_factory_run_per_project(self):
        sid = self._story()
        self._populate(sid, chapters=2, scenes_per=2)
        run = sc.produce_story(sid, self.settings, object())

        done = service.get_run(run.id)
        self.assertEqual(done.status, "COMPLETED")
        self.assertEqual(done.scope, "PRODUCE")
        self.assertEqual(len(done.compiled_project_ids_json), 2)
        self.assertEqual(sorted(self.started_projects), sorted(done.compiled_project_ids_json))
        cps = {c.stage: c.status for c in service.get_checkpoints(run.id)}
        self.assertEqual(cps, {"COMPILING": "COMPLETED", "PRODUCING": "COMPLETED"})
        self.assertEqual(service.get_story(sid).status, "PRODUCING")

    def test_produce_blocked_by_cost_guard(self):
        sid = self._story(config={"cost_guard": {"max_total_usd": 0.00001, "block_on_exceed": True}})
        self._populate(sid, chapters=2, scenes_per=2)
        with self.assertRaises(ValidationError):
            sc.produce_story(sid, self.settings, object())

    def test_retry_reuses_the_runs_recorded_projects(self):
        sid = self._story()
        self._populate(sid, chapters=2, scenes_per=2)
        run = sc.produce_story(sid, self.settings, object())
        ids_first = service.get_run(run.id).compiled_project_ids_json
        self.started_projects.clear()

        # simulate a failed produce run, then retry via the same sync path
        service.set_run_fields(run.id, status="FAILED", failed_stage="PRODUCING")
        sc._execute_story_produce_sync(run.id, sid, self.settings, object())

        self.assertEqual(service.get_run(run.id).compiled_project_ids_json, ids_first)
        with self.Session() as db:
            self.assertEqual(db.query(Project).count(), 2)  # no new projects on retry

    def test_test_render_uses_first_scenes_preview_profile_and_no_chapter_link(self):
        sid = self._story()
        self._populate(sid, chapters=3, scenes_per=3)  # 9 scenes total
        run = sc.produce_story(sid, self.settings, object(), test=True)

        done = service.get_run(run.id)
        self.assertEqual(done.status, "COMPLETED")
        self.assertEqual(len(done.compiled_project_ids_json), 1)
        pid = done.compiled_project_ids_json[0]
        with self.Session() as db:
            proj = db.get(Project, pid)
        self.assertEqual(len(proj.beat_plan_json["beats"]), sc._TEST_MAX_SCENES)  # 5, not 9
        self.assertEqual(proj.beat_plan_json["config"]["render"]["profile"], "PREVIEW")
        self.assertIn("TEST", proj.name)
        # a test never touches the chapter links or the story status
        self.assertTrue(all(c.compiled_project_id is None for c in service.list_chapters(sid)))
        self.assertNotEqual(service.get_story(sid).status, "PRODUCING")

    def test_test_render_skips_the_cost_guard(self):
        sid = self._story(config={"cost_guard": {"max_total_usd": 0.00001, "block_on_exceed": True}})
        self._populate(sid, chapters=2, scenes_per=2)
        run = sc.produce_story(sid, self.settings, object(), test=True)  # must not raise
        self.assertEqual(service.get_run(run.id).status, "COMPLETED")

    def test_compiled_view_surfaces_a_test_render(self):
        sid = self._story()
        self._populate(sid, chapters=2, scenes_per=2)
        run = sc.produce_story(sid, self.settings, object(), test=True)
        pid = service.get_run(run.id).compiled_project_ids_json[0]
        with self.Session() as db:
            db.add(FactoryRun(project_id=pid, status="RENDERING"))
            db.commit()
        view = sc._compiled_view(sid)
        self.assertEqual(len(view), 1)
        self.assertTrue(view[0]["is_test"])
        self.assertEqual(view[0]["factory_run"]["status"], "RENDERING")

    def test_compiled_view_reports_factory_run_status(self):
        sid = self._story()
        self._populate(sid, chapters=1, scenes_per=2)
        sc.compile_story(sid)
        pid = service.list_chapters(sid)[0].compiled_project_id
        with self.Session() as db:
            db.add(FactoryRun(project_id=pid, status="RENDERING"))
            db.commit()
        view = sc._compiled_view(sid)
        self.assertEqual(len(view), 1)
        self.assertEqual(view[0]["factory_run"]["status"], "RENDERING")


if __name__ == "__main__":
    unittest.main()
