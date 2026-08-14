"""Loads examples/video_factory/{beats,assets,motion,composition}.json and
validates them against the real Pydantic contracts (app.modules.beat,
app.modules.asset, app.modules.motion, app.modules.composition), then
cross-checks that the four files actually reference each other correctly:

    beats.json -> asset resolution -> motion contract -> composition.json

This proves the domain contracts built in Tasks 02-08 compose into one
coherent plan *before* any rendering exists to prove it end-to-end. No
rendering, no new production code, no new abstractions -- these tests only
read the four JSON files and call `.model_validate_json()`/`model_validate()`
plus a few dict/set comparisons "resolving" references between files (a
handful of local dict lookups, not a new "asset resolution" module).
"""

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.modules.asset.schemas import AssetOut
from app.modules.beat.schemas import BeatPlan
from app.modules.composition.schemas import CompositionPlan
from app.modules.motion.schemas import MotionPlan

EXAMPLE_DIR = Path(__file__).resolve().parents[3] / "examples" / "video_factory"


def _load_json(filename: str):
    return json.loads((EXAMPLE_DIR / filename).read_text(encoding="utf-8"))


def _load_beat_plan() -> BeatPlan:
    return BeatPlan.model_validate(_load_json("beats.json"))


def _load_assets() -> list[AssetOut]:
    return [AssetOut.model_validate(entry) for entry in _load_json("assets.json")]


def _load_motion_plans() -> list[MotionPlan]:
    return [MotionPlan.model_validate(entry) for entry in _load_json("motion.json")]


def _load_composition_plan() -> CompositionPlan:
    return CompositionPlan.model_validate(_load_json("composition.json"))


class GoldenSampleFilesExistTests(unittest.TestCase):
    def test_all_four_json_files_exist(self):
        for filename in ("beats.json", "assets.json", "motion.json", "composition.json"):
            self.assertTrue((EXAMPLE_DIR / filename).is_file(), f"missing {filename}")

    def test_referenced_local_asset_files_exist_on_disk(self):
        # "local asset references" -- the paths in assets.json should be
        # real, resolvable files, not just plausible-looking strings.
        repo_root = EXAMPLE_DIR.parents[1]
        for asset in _load_assets():
            self.assertTrue((repo_root / asset.path).is_file(), f"missing asset file: {asset.path}")


class BeatsJsonValidationTests(unittest.TestCase):
    def test_beats_json_is_a_valid_beat_plan(self):
        plan = _load_beat_plan()
        self.assertEqual(len(plan.beats), 5)

    def test_beats_total_duration_is_thirty_seconds(self):
        plan = _load_beat_plan()
        self.assertEqual(plan.total_duration, 30.0)

    def test_every_beat_has_narration_text(self):
        plan = _load_beat_plan()
        for beat in plan.beats:
            self.assertTrue(beat.narration and beat.narration.strip(), f"{beat.id} has no narration")

    def test_every_beat_has_a_visual_hint(self):
        plan = _load_beat_plan()
        for beat in plan.beats:
            self.assertTrue(beat.visual_hint and beat.visual_hint.strip(), f"{beat.id} has no visual_hint")


class AssetsJsonValidationTests(unittest.TestCase):
    def test_assets_json_entries_are_valid_asset_out_shapes(self):
        assets = _load_assets()
        self.assertEqual(len(assets), 5)

    def test_asset_ids_are_unique(self):
        assets = _load_assets()
        ids = [asset.id for asset in assets]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_assets_are_marked_ready(self):
        for asset in _load_assets():
            self.assertTrue(asset.is_ready)


class MotionJsonValidationTests(unittest.TestCase):
    def test_motion_json_entries_are_valid_motion_plans(self):
        plans = _load_motion_plans()
        self.assertEqual(len(plans), 5)

    def test_five_distinct_motion_presets_are_used(self):
        plans = _load_motion_plans()
        presets = {plan.preset for plan in plans}
        self.assertEqual(len(presets), 5, "motion.json must use 5 distinct presets")


class CompositionJsonValidationTests(unittest.TestCase):
    def test_composition_json_is_a_valid_composition_plan(self):
        plan = _load_composition_plan()
        self.assertEqual(len(plan.scenes), 5)

    def test_composition_total_duration_is_thirty_seconds(self):
        plan = _load_composition_plan()
        self.assertEqual(plan.total_duration, 30.0)

    def test_composition_has_a_music_reference(self):
        plan = _load_composition_plan()
        self.assertIsNotNone(plan.music_path)
        self.assertTrue(plan.music_path.strip())

    def test_composition_has_a_narration_reference(self):
        plan = _load_composition_plan()
        self.assertIsNotNone(plan.narration_script)
        self.assertTrue(plan.narration_script.strip())

    def test_composition_has_a_caption_preset(self):
        plan = _load_composition_plan()
        self.assertIsNotNone(plan.caption_preset)

    def test_composition_scenes_ordering_is_contiguous(self):
        # Enforced by CompositionPlan's own model_validator -- if
        # _load_composition_plan() above didn't raise, this already holds;
        # asserted again explicitly for a clear, literal ordering check.
        plan = _load_composition_plan()
        self.assertEqual([scene.order for scene in plan.ordered_scenes()], [1, 2, 3, 4, 5])


class ChainIntegrityTests(unittest.TestCase):
    """beats.json -> motion contract -> composition.json: proves the four
    files aren't just independently-valid, but actually describe the *same*
    five-beat video, consistently, end to end. Beat no longer carries a
    resolved asset_id/motion preset/caption/sfx (those are Composition/Scene
    concerns, assigned by a later pipeline step) -- what's still checked
    here is id/order/duration/narration agreement between beats.json and
    composition.json, plus composition.json's own internal consistency with
    motion.json.
    """

    def setUp(self):
        self.beat_plan = _load_beat_plan()
        self.assets = _load_assets()
        self.motion_plans = _load_motion_plans()
        self.composition = _load_composition_plan()
        self.assets_by_id = {asset.id: asset for asset in self.assets}
        self.beats_by_id = {beat.id: beat for beat in self.beat_plan.beats}
        self.motion_by_preset = {plan.preset.value: plan for plan in self.motion_plans}

    def test_every_scene_references_a_valid_beat_id(self):
        for scene in self.composition.scenes:
            self.assertIn(scene.beat_id, self.beats_by_id, f"{scene.id} references unknown beat {scene.beat_id}")

    def test_scene_order_matches_beat_order(self):
        for scene in self.composition.scenes:
            beat = self.beats_by_id[scene.beat_id]
            self.assertEqual(scene.order, beat.order)

    def test_every_scene_references_a_valid_asset_id(self):
        for scene in self.composition.scenes:
            self.assertIn(
                scene.source_asset_id, self.assets_by_id, f"{scene.id} references unknown asset {scene.source_asset_id}"
            )

    def test_scene_duration_matches_beat_duration(self):
        for scene in self.composition.scenes:
            beat = self.beats_by_id[scene.beat_id]
            self.assertEqual(scene.duration, beat.duration)

    def test_scene_motion_preset_name_is_a_real_motion_json_preset(self):
        motion_preset_values = {plan.preset.value for plan in self.motion_plans}
        for scene in self.composition.scenes:
            self.assertIn(scene.motion.preset_name, motion_preset_values)

    def test_scene_motion_numeric_values_match_the_motion_json_entry(self):
        # Not just "the preset name looks right" -- the embedded
        # scale/position/rotation/easing must be identical to the
        # corresponding motion.json MotionPlan, proving composition.json's
        # per-scene motion was genuinely drawn from motion.json.
        for scene in self.composition.scenes:
            motion_plan = self.motion_by_preset[scene.motion.preset_name]
            self.assertEqual(scene.motion.scale.start, motion_plan.scale.start)
            self.assertEqual(scene.motion.scale.end, motion_plan.scale.end)
            self.assertEqual(scene.motion.position.x_start, motion_plan.position.x_start)
            self.assertEqual(scene.motion.position.y_start, motion_plan.position.y_start)
            self.assertEqual(scene.motion.position.x_end, motion_plan.position.x_end)
            self.assertEqual(scene.motion.position.y_end, motion_plan.position.y_end)
            self.assertEqual(scene.motion.rotation.start, motion_plan.rotation.start)
            self.assertEqual(scene.motion.rotation.end, motion_plan.rotation.end)
            self.assertEqual(scene.motion.easing.value, motion_plan.easing.value)

    def test_motion_plan_duration_matches_the_beat_it_was_built_for(self):
        for scene in self.composition.scenes:
            beat = self.beats_by_id[scene.beat_id]
            motion_plan = self.motion_by_preset[scene.motion.preset_name]
            self.assertEqual(motion_plan.duration, beat.duration)

    def test_five_beats_five_assets_five_motion_presets_five_scenes(self):
        # The literal shape the acceptance criteria asks for.
        self.assertEqual(len(self.beat_plan.beats), 5)
        self.assertEqual(len(self.assets), 5)
        self.assertEqual(len({p.preset for p in self.motion_plans}), 5)
        self.assertEqual(len(self.composition.scenes), 5)

    def test_all_three_files_agree_on_thirty_second_total_duration(self):
        self.assertEqual(self.beat_plan.total_duration, 30.0)
        self.assertEqual(self.composition.total_duration, 30.0)
        self.assertEqual(sum(plan.duration for plan in self.motion_plans), 30.0)

    def test_narration_script_contains_every_beat_narration(self):
        for beat in self.beat_plan.beats:
            self.assertIn(beat.narration, self.composition.narration_script)


class InvalidVariantsAreRejectedTests(unittest.TestCase):
    """Negative tests: the golden sample's own validity isn't a fluke of
    lax schemas -- deliberately-broken variants of the same data must fail.
    """

    def test_composition_with_duplicate_scene_order_is_rejected(self):
        data = _load_json("composition.json")
        data["scenes"][1]["order"] = data["scenes"][0]["order"]
        with self.assertRaises(ValidationError):
            CompositionPlan.model_validate(data)

    def test_composition_with_missing_asset_is_rejected(self):
        data = _load_json("composition.json")
        data["scenes"][0]["source_asset_id"] = 0
        with self.assertRaises(ValidationError):
            CompositionPlan.model_validate(data)

    def test_motion_with_out_of_range_scale_is_rejected(self):
        data = _load_json("motion.json")
        data[0]["scale"]["end"] = 10.0
        with self.assertRaises(ValidationError):
            MotionPlan.model_validate(data[0])

    def test_beats_with_non_contiguous_ordering_is_rejected(self):
        data = _load_json("beats.json")
        data["beats"][-1]["order"] = 99
        with self.assertRaises(ValidationError):
            BeatPlan.model_validate(data)


if __name__ == "__main__":
    unittest.main()
