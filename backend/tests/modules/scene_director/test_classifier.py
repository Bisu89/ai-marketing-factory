"""Tests for app.modules.scene_director.classifier (AI Storytelling Studio
plan, Phase 0). Pure functions, no DB/FFmpeg/AI -- every test builds plain
SceneAnalysisInput/SceneDirectorConfig objects directly, matching
app.modules.quality.analyzer's own pure-contract test style.
"""

import unittest

from app.modules.scene_director.classifier import classify_scene, classify_scenes
from app.modules.scene_director.schemas import SceneAnalysisInput, SceneDirectorConfig


def _scene(sid="s1", order=1, **kw) -> SceneAnalysisInput:
    base = dict(id=sid, order=order, scene_type="body", narration="Something happens.",
                emotion="neutral", character_count=1, duration_hint=6.0)
    base.update(kw)
    return SceneAnalysisInput(**base)


class VisualModeDecisionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = SceneDirectorConfig()

    def test_quiet_low_stakes_scene_is_still(self):
        c = classify_scene(_scene(narration="A quiet morning. Birds sing softly.", emotion="calm"), self.cfg)
        self.assertEqual(c.visual_mode, "STILL")
        self.assertEqual(c.visual_priority, "low")

    def test_battle_scene_with_real_movement_is_ai_video(self):
        c = classify_scene(
            _scene(
                scene_type="climax",
                narration="He drew his sword and charged as arrows fired and horses fell and men ran screaming!",
                emotion="terror", camera="handheld tracking shot", character_count=10, duration_hint=16.0,
            ),
            self.cfg,
        )
        self.assertEqual(c.visual_mode, "AI_VIDEO")
        self.assertGreaterEqual(c.movement_score, self.cfg.min_movement_for_video)

    def test_high_emotion_but_no_movement_is_never_ai_video(self):
        # Audio-first: a devastating emotional reveal with NO physical action
        # is a great STILL close-up, not a video.
        c = classify_scene(
            _scene(
                scene_type="reveal",
                narration="She stared at the letter. Her father had known all along. She had trusted him.",
                emotion="betrayal", character_count=1, dialogue_line_count=0, duration_hint=12.0,
            ),
            self.cfg,
        )
        self.assertNotEqual(c.visual_mode, "AI_VIDEO")
        self.assertIn(c.visual_mode, ("STILL", "STILL_WITH_MOTION"))

    def test_disabled_director_defaults_everything_to_motion(self):
        cfg = SceneDirectorConfig(enabled=False)
        for s in ("hook", "climax", "body"):
            c = classify_scene(_scene(scene_type=s), cfg)
            self.assertEqual(c.visual_mode, "STILL_WITH_MOTION")

    def test_low_importance_repeated_context_scene_gets_reuse_hint(self):
        c = classify_scene(
            _scene(scene_type="transition", narration="Time passed.", emotion="neutral",
                   character_count=1, same_location_as_prev=True, same_characters_as_prev=True, duration_hint=3.0),
            self.cfg,
        )
        self.assertEqual(c.visual_mode, "STILL")
        self.assertTrue(c.reuse_existing_asset)

    def test_motion_preset_hint_is_always_a_valid_beat_preset_name(self):
        from app.modules.scene_director.schemas import MOTION_HINTS
        for st, nar, emo in [
            ("body", "Nothing much.", "neutral"),
            ("climax", "He ran and fought and fell.", "rage"),
            ("reveal", "The truth landed like a blow.", "grief"),
        ]:
            c = classify_scene(_scene(scene_type=st, narration=nar, emotion=emo), self.cfg)
            self.assertIn(c.motion_preset_hint, MOTION_HINTS)


class AiVideoBudgetTests(unittest.TestCase):
    def _many_action_scenes(self, n):
        return [
            _scene(f"s{i}", i, scene_type="climax",
                   narration="They charged and fought and ran and fell and fired arrows screaming!",
                   emotion="terror", camera="tracking", character_count=8, duration_hint=12.0)
            for i in range(1, n + 1)
        ]

    def test_ratio_and_hard_cap_demote_lowest_scoring_candidates(self):
        cfg = SceneDirectorConfig(ai_video_max_ratio=0.25, ai_video_hard_cap=12)
        scenes = self._many_action_scenes(8)  # budget = min(12, round(0.25*8)) = 2
        rep = classify_scenes(scenes, cfg)
        self.assertLessEqual(rep.ai_video_count, 2)
        self.assertEqual(len(rep.demoted_scene_ids), max(0, 8 - rep.ai_video_count - rep.still_count))
        # demoted scenes became STILL_WITH_MOTION, not STILL
        demoted = {c.scene_id for c in rep.scenes if c.scene_id in rep.demoted_scene_ids}
        for c in rep.scenes:
            if c.scene_id in demoted:
                self.assertEqual(c.visual_mode, "STILL_WITH_MOTION")

    def test_ratio_zero_means_never_ai_video(self):
        cfg = SceneDirectorConfig(ai_video_max_ratio=0.0, ai_video_hard_cap=99)
        rep = classify_scenes(self._many_action_scenes(6), cfg)
        self.assertEqual(rep.ai_video_count, 0)

    def test_rollups_are_consistent(self):
        cfg = SceneDirectorConfig()
        scenes = self._many_action_scenes(3) + [_scene("q1", 4, emotion="calm", narration="A still lake.")]
        rep = classify_scenes(scenes, cfg)
        self.assertEqual(
            rep.ai_video_count + rep.still_with_motion_count + rep.still_count, len(scenes)
        )


class DeterminismTests(unittest.TestCase):
    def test_same_input_same_output(self):
        cfg = SceneDirectorConfig()
        scenes = [
            _scene("a", 1, scene_type="hook", narration="It begins.", emotion="tension"),
            _scene("b", 2, scene_type="climax", narration="He charged and fell.", emotion="rage", character_count=5),
            _scene("c", 3, scene_type="ending", narration="And so it ended.", emotion="grief"),
        ]
        r1 = classify_scenes(scenes, cfg).model_dump()
        r2 = classify_scenes(scenes, cfg).model_dump()
        self.assertEqual(r1, r2)


class ConfigValidationTests(unittest.TestCase):
    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            SceneDirectorConfig(w_importance=0.5, w_movement=0.5, w_emotion=0.5, w_complexity=0.5)

    def test_still_motion_threshold_cannot_exceed_video_threshold(self):
        with self.assertRaises(ValueError):
            SceneDirectorConfig(still_motion_threshold=80.0, video_threshold=50.0)


if __name__ == "__main__":
    unittest.main()
