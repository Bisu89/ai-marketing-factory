import tempfile
import unittest
from pathlib import Path

from app.modules.composition.schemas import (
    CompositionPlan,
    OutputFormat,
    PositionRange,
    Scene,
    SceneMotion,
)
from app.modules.composition.service import build_composition_plan, load_composition_json, save_composition_json


def _scene(scene_id: str, order: int, duration: float, asset_id: int) -> Scene:
    return Scene(
        id=scene_id,
        order=order,
        beat_id=f"beat_{order:02d}",
        duration=duration,
        source_asset_id=asset_id,
        motion=SceneMotion(
            preset_name="slow_push_in",
            scale={"start": 1.0, "end": 1.08},
            position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.52, y_end=0.48),
        ),
        output_format=OutputFormat(width=1080, height=1920, fps=30.0),
    )


class BuildCompositionPlanTests(unittest.TestCase):
    def test_composition_creation_from_scenes(self):
        plan = build_composition_plan(
            [_scene("scene_01", 1, 4.0, 101), _scene("scene_02", 2, 20.0, 102)],
            video_id=7,
            narration_script="A short vertical-video script.",
            voice="en-US-GuyNeural",
            language="english",
        )
        self.assertIsInstance(plan, CompositionPlan)
        self.assertEqual(plan.video_id, 7)
        self.assertEqual(len(plan.scenes), 2)
        self.assertEqual(plan.total_duration, 24.0)

    def test_composition_creation_defaults(self):
        plan = build_composition_plan([_scene("scene_01", 1, 4.0, 101)])
        self.assertIsNone(plan.video_id)
        self.assertIsNone(plan.narration_script)
        self.assertEqual(plan.voice, "en-US-GuyNeural")


class CompositionJsonFileTests(unittest.TestCase):
    def test_save_and_load_round_trip_via_composition_json(self):
        plan = build_composition_plan(
            [
                _scene("scene_01", 1, 4.0, 101),
                _scene("scene_02", 2, 20.0, 102),
                _scene("scene_03", 3, 5.0, 103),
            ],
            video_id=7,
            narration_script="A short vertical-video script.",
        )

        with tempfile.TemporaryDirectory() as tmp:
            composition_path = Path(tmp) / "composition.json"
            save_composition_json(plan, composition_path)

            self.assertTrue(composition_path.exists())
            restored = load_composition_json(composition_path)

            self.assertEqual(restored, plan)
            self.assertEqual(restored.total_duration, 29.0)
            self.assertEqual(
                [s.id for s in restored.ordered_scenes()], ["scene_01", "scene_02", "scene_03"]
            )

    def test_beats_json_and_composition_json_coexist_in_one_project_directory(self):
        # Mirrors the acceptance criteria's project/ layout:
        #   project/beats.json
        #   project/composition.json
        # Importing app.modules.beat here is fine -- this is a test
        # exercising two independent modules together, not production code
        # inside either module (the "modules never import modules" rule
        # applies to app/modules/*, not to tests).
        from app.modules.beat.schemas import Beat, BeatPlan, BeatType
        from app.modules.beat.service import save_beats_json

        beat_plan = BeatPlan(
            script_text="Anna and Tom's story.",
            beats=[
                Beat(id="beat_01", order=1, duration=4.0, type=BeatType.HOOK, narration="Meet Anna and Tom."),
                Beat(id="beat_02", order=2, duration=20.0, type=BeatType.BODY, narration="Their story unfolds."),
            ],
        )
        composition_plan = build_composition_plan(
            [_scene("scene_01", 1, 4.0, 101), _scene("scene_02", 2, 20.0, 102)],
            narration_script=beat_plan.script_text,
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            save_beats_json(beat_plan, project_dir / "beats.json")
            save_composition_json(composition_plan, project_dir / "composition.json")

            self.assertTrue((project_dir / "beats.json").exists())
            self.assertTrue((project_dir / "composition.json").exists())
            self.assertEqual(sorted(p.name for p in project_dir.iterdir()), ["beats.json", "composition.json"])


if __name__ == "__main__":
    unittest.main()
