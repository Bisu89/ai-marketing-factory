"""Tests for the story pipeline composition root
(app/api/v1/endpoints/story_pipeline.py, feature 132) -- the Scene Director
wired to real StoryScene rows + the pre-flight cost/budget guard. Route
handlers called as plain functions against one in-memory DB, this
codebase's established convention (see tests/api/test_series_project.py).
"""

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import story_pipeline as sp
from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.story import service
from app.modules.story.models import (
    Episode,
    Story,
    StoryChapter,
    StoryCharacter,
    StoryLocation,
    StoryRun,
    StoryScene,
)

_TABLES = [
    Episode.__table__, Story.__table__, StoryChapter.__table__, StoryScene.__table__,
    StoryCharacter.__table__, StoryLocation.__table__, StoryRun.__table__,
]

# A battle scene -- lots of movement verbs + a dynamic camera -> AI_VIDEO.
_BATTLE = (
    "The cavalry charge across the field as arrows rain down. Men run and fall, "
    "shields shatter, riders are thrown. He draws his sword and strikes."
)
# A quiet reveal -- high emotion, zero movement -> STILL_WITH_MOTION (audio-first).
_REVEAL = "She reads the letter in silence. The betrayal is complete. Her face does not move."
_CALM = "The council speaks of grain and taxes. Nothing is decided."


class _PipelineTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine, tables=_TABLES)
        self.Session = sessionmaker(bind=self.engine)
        self.patcher = patch("app.modules.story.service.SessionLocal", self.Session)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()

    def _story(self, *, config=None, budget=None) -> int:
        st = service.create_story(
            title="Cannae", mode="HISTORY", episode_id=None,
            project_config_json=config or {}, story_bible_json={}, style_bible_json={},
            budget_usd=budget, production_profile="BALANCED", reference_notes=None,
            logline=None, genre=None, content_idea_id=None,
        )
        return st.id

    def _chapter_with_scenes(self, story_id: int, scene_specs: list[dict]) -> int:
        chap = service.add_chapter(story_id, order=1, title="The Trap")
        for i, spec in enumerate(scene_specs, start=1):
            service.add_scene(
                chap.id, order=i,
                narration=spec.get("narration", ""),
                scene_type=spec.get("scene_type"),
                emotion=spec.get("emotion"),
                camera=spec.get("camera"),
                dialogue_json=spec.get("dialogue_json", []),
                character_ids_json=spec.get("character_ids_json", []),
                visual_mode=spec.get("visual_mode", "STILL_WITH_MOTION"),
                visual_mode_source=spec.get("visual_mode_source", "AUTO"),
                duration_hint=spec.get("duration_hint", 6.0),
            )
        return chap.id


# A ratio that lets a 2-scene story keep 1 AI_VIDEO (default 0.15 rounds to 0
# below 4 scenes -- correct, but not what these small fixtures are testing).
_ALLOW_VIDEO = {"scene_classification": {"ai_video_max_ratio": 0.5}}


class ClassifySceneTests(_PipelineTestCase):
    def test_movement_scene_becomes_ai_video_emotion_scene_does_not(self):
        sid = self._story(config=_ALLOW_VIDEO)
        cid = self._chapter_with_scenes(sid, [
            {"narration": _BATTLE, "scene_type": "CLIMAX", "camera": "tracking shot", "emotion": "fury"},
            {"narration": _REVEAL, "scene_type": "REVEAL", "emotion": "betrayal"},
        ])
        resp = sp.classify_and_persist(sid)
        self.assertEqual(resp.scenes_total, 2)
        self.assertEqual(resp.scenes_updated, 2)
        rows = service.list_scenes(cid)
        self.assertEqual(rows[0].visual_mode, "AI_VIDEO")
        self.assertEqual(rows[1].visual_mode, "STILL_WITH_MOTION")
        # scores persisted
        self.assertIsNotNone(rows[0].composite_score)
        self.assertGreater(rows[0].movement_score, rows[1].movement_score)

    def test_user_frozen_scene_is_not_touched(self):
        sid = self._story(config=_ALLOW_VIDEO)
        cid = self._chapter_with_scenes(sid, [
            {"narration": _BATTLE, "scene_type": "CLIMAX", "camera": "tracking shot",
             "visual_mode": "STILL", "visual_mode_source": "USER"},
        ])
        resp = sp.classify_and_persist(sid)
        self.assertEqual(resp.scenes_frozen, 1)
        row = service.list_scenes(cid)[0]
        self.assertEqual(row.visual_mode, "STILL")           # frozen -- kept
        self.assertIsNotNone(row.composite_score)            # scores still filled

    def test_ai_video_budget_demotes_extra_candidates(self):
        sid = self._story(config={"scene_classification": {"ai_video_max_ratio": 0.5, "ai_video_hard_cap": 1}})
        self._chapter_with_scenes(sid, [
            {"narration": _BATTLE, "scene_type": "CLIMAX", "camera": "tracking shot", "emotion": "fury"},
            {"narration": _BATTLE, "scene_type": "CLIMAX", "camera": "handheld chase", "emotion": "rage"},
        ])
        resp = sp.classify_and_persist(sid)
        self.assertEqual(resp.ai_video_count, 1)
        self.assertEqual(len(resp.demoted_scene_ids), 1)

    def test_no_scenes_raises(self):
        sid = self._story()
        service.add_chapter(sid, order=1)
        with self.assertRaises(ValidationError):
            sp.classify_and_persist(sid)


class CostEstimateTests(_PipelineTestCase):
    def test_verdict_ok_without_a_cap(self):
        sid = self._story()
        self._chapter_with_scenes(sid, [{"narration": _CALM}, {"narration": _REVEAL, "emotion": "grief"}])
        sp.classify_and_persist(sid)
        cost = sp.estimate_cost(sid)
        self.assertEqual(cost.verdict, "OK")
        self.assertEqual(cost.cap_source, "none")
        self.assertEqual(cost.scene_counts["scenes_total"], 2)

    def test_tiny_budget_blocks(self):
        sid = self._story(config={"cost_guard": {"max_total_usd": 0.0001, "block_on_exceed": True}})
        self._chapter_with_scenes(sid, [{"narration": _CALM} for _ in range(5)])
        sp.classify_and_persist(sid)
        cost = sp.estimate_cost(sid)
        self.assertEqual(cost.verdict, "BLOCK")
        self.assertEqual(cost.cap_source, "cost_guard")

    def test_story_budget_used_as_cap_when_no_cost_guard(self):
        sid = self._story(budget=0.0001)
        self._chapter_with_scenes(sid, [{"narration": _CALM} for _ in range(3)])
        sp.classify_and_persist(sid)
        cost = sp.estimate_cost(sid)
        self.assertIn(cost.verdict, ("WARN", "BLOCK"))
        self.assertEqual(cost.cap_source, "story_budget")

    def test_planned_story_excludes_planning_llm_from_the_estimate(self):
        # Once scenes exist, the planning LLM calls are done (or, for an
        # imported story, will never run) -- the forward-looking estimate
        # must not bill them again.
        sid = self._story()
        self._chapter_with_scenes(sid, [{"narration": _CALM} for _ in range(6)])
        sp.classify_and_persist(sid)
        cost = sp.estimate_cost(sid)
        # LLM cost is now just the per-project metadata rewrite -- far below
        # the ~$0.9 the full planning buckets would produce.
        self.assertLess(cost.estimate["llm_usd"], 0.10)
        self.assertTrue(any("Kế hoạch đã xong" in n for n in cost.notes))

    def test_unplanned_story_still_includes_planning_llm(self):
        sid = self._story()
        service.add_chapter(sid, order=1, title="c1")  # a chapter but no scenes
        cost = sp.estimate_cost(sid)
        self.assertGreater(cost.estimate["llm_usd"], 0.10)

    def test_scene_plan_combines_rows_and_cost(self):
        sid = self._story(config=_ALLOW_VIDEO)
        self._chapter_with_scenes(sid, [
            {"narration": _BATTLE, "scene_type": "CLIMAX", "camera": "tracking shot", "emotion": "fury"},
            {"narration": _CALM},
        ])
        sp.classify_and_persist(sid)
        plan = sp.scene_plan(sid)
        self.assertEqual(len(plan.scenes), 2)
        self.assertEqual(plan.scenes[0].visual_mode, "AI_VIDEO")
        self.assertIsNone(plan.scenes[0].est_cost_usd)         # AI_VIDEO unpriced
        self.assertEqual(plan.scenes[1].est_cost_usd, sp.IMAGE_COST_USD)
        self.assertEqual(plan.cost.story_id, sid)


class ResolveConfigTests(_PipelineTestCase):
    def test_bad_config_blob_is_a_validation_error(self):
        sid = self._story(config={"render": {"profile": "NOT_A_REAL_PROFILE"}})
        with self.assertRaises(ValidationError):
            sp.get_resolved_config(sid)

    def test_empty_blob_returns_defaults(self):
        sid = self._story(config={})
        pc = sp.get_resolved_config(sid)
        self.assertTrue(pc.scene_classification.enabled)


if __name__ == "__main__":
    unittest.main()
