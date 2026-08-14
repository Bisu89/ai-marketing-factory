import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.modules.beat.schemas import (
    DEFAULT_PROJECT_CONFIG,
    Beat,
    BeatMotionPreset,
    BeatPlan,
    BeatType,
    effective_motion_preset,
)
from app.modules.beat.service import load_beats_json, save_beats_json


def _make_beat(
    id_: str = "beat_01",
    order: int = 1,
    duration: float = 4.0,
    type_: BeatType = BeatType.HOOK,
    narration: str | None = "Meet Anna and Tom.",
    visual_hint: str | None = "emotional couple, road trip",
    asset_id: int | None = None,
    motion_preset: BeatMotionPreset | None = None,
    narration_asset_id: int | None = None,
) -> Beat:
    kwargs = dict(
        id=id_,
        order=order,
        duration=duration,
        type=type_,
        narration=narration,
        visual_hint=visual_hint,
        asset_id=asset_id,
        narration_asset_id=narration_asset_id,
    )
    if motion_preset is not None:
        kwargs["motion_preset"] = motion_preset
    return Beat(**kwargs)


class BeatValidationTests(unittest.TestCase):
    def test_valid_beat_is_accepted(self):
        beat = _make_beat()
        self.assertEqual(beat.id, "beat_01")
        self.assertEqual(beat.order, 1)
        self.assertEqual(beat.duration, 4.0)
        self.assertEqual(beat.type, BeatType.HOOK)
        self.assertEqual(beat.narration, "Meet Anna and Tom.")
        self.assertEqual(beat.visual_hint, "emotional couple, road trip")

    def test_optional_fields_default_to_none(self):
        beat = Beat(id="beat_01", order=1, duration=4.0, type=BeatType.BODY)
        self.assertIsNone(beat.narration)
        self.assertIsNone(beat.visual_hint)
        self.assertIsNone(beat.asset_id)
        self.assertIsNone(beat.narration_asset_id)

    def test_valid_positive_narration_asset_id_accepted(self):
        beat = _make_beat(narration_asset_id=77)
        self.assertEqual(beat.narration_asset_id, 77)

    def test_zero_narration_asset_id_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(narration_asset_id=0)

    def test_negative_narration_asset_id_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(narration_asset_id=-3)

    def test_missing_motion_preset_is_none_and_resolves_to_static_by_default(self):
        # Task 12 (see docs/features/39-project-templates.md): an unset
        # motion_preset means "inherit the project's default", not a
        # hardcoded STATIC -- but DEFAULT_PROJECT_CONFIG's own default IS
        # STATIC, so the end-to-end resolved behavior is unchanged from
        # before this task for any project with no template applied.
        beat = Beat(id="beat_01", order=1, duration=4.0, type=BeatType.BODY)
        self.assertIsNone(beat.motion_preset)
        self.assertEqual(effective_motion_preset(beat, DEFAULT_PROJECT_CONFIG), BeatMotionPreset.STATIC)

    def test_all_six_motion_presets_are_valid(self):
        for preset in (
            BeatMotionPreset.STATIC,
            BeatMotionPreset.SLOW_PUSH_IN,
            BeatMotionPreset.SLOW_PULL_OUT,
            BeatMotionPreset.PAN_LEFT,
            BeatMotionPreset.PAN_RIGHT,
            BeatMotionPreset.ZOOM_AND_PAN,
        ):
            beat = _make_beat(motion_preset=preset)
            self.assertEqual(beat.motion_preset, preset)

    def test_unknown_motion_preset_rejected(self):
        with self.assertRaises(ValidationError):
            Beat(id="beat_01", order=1, duration=4.0, type=BeatType.BODY, motion_preset="KAMEHAMEHA")

    def test_valid_positive_asset_id_accepted(self):
        beat = _make_beat(asset_id=42)
        self.assertEqual(beat.asset_id, 42)

    def test_zero_asset_id_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(asset_id=0)

    def test_negative_asset_id_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(asset_id=-1)

    def test_empty_id_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(id_="")

    def test_whitespace_only_id_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(id_="   ")

    def test_invalid_order_below_one_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(order=0)

    def test_invalid_order_negative_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(order=-1)

    def test_invalid_type_rejected(self):
        with self.assertRaises(ValidationError):
            Beat(id="beat_01", order=1, duration=4.0, type="NOT_A_REAL_TYPE")

    def test_invalid_duration_zero_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(duration=0.0)

    def test_invalid_duration_negative_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(duration=-2.0)

    def test_invalid_duration_above_upper_bound_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(duration=121.0)

    def test_whitespace_only_narration_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(narration="   ")

    def test_whitespace_only_visual_hint_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(visual_hint="   ")

    def test_all_seven_beat_types_are_valid(self):
        for type_ in (
            BeatType.HOOK,
            BeatType.SETUP,
            BeatType.BUILD,
            BeatType.REVEAL,
            BeatType.REACTION,
            BeatType.ENDING,
            BeatType.BODY,
        ):
            beat = _make_beat(type_=type_)
            self.assertEqual(beat.type, type_)


class BeatPlanValidationTests(unittest.TestCase):
    def test_valid_multiple_beats_accepted(self):
        plan = BeatPlan(
            beats=[
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                _make_beat("beat_02", 2, 20.0, BeatType.BUILD),
                _make_beat("beat_03", 3, 5.0, BeatType.ENDING),
            ]
        )
        self.assertEqual(len(plan.beats), 3)

    def test_sequential_order_accepted_regardless_of_list_position(self):
        plan = BeatPlan(
            beats=[
                _make_beat("beat_02", 2, 5.0, BeatType.BODY),
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
            ]
        )
        self.assertEqual([b.id for b in plan.ordered_beats()], ["beat_01", "beat_02"])

    def test_empty_beats_list_rejected(self):
        with self.assertRaises(ValidationError):
            BeatPlan(beats=[])

    def test_duplicate_id_rejected(self):
        with self.assertRaises(ValidationError):
            BeatPlan(
                beats=[
                    _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                    _make_beat("beat_01", 2, 5.0, BeatType.BODY),  # duplicate id
                ]
            )

    def test_duplicate_order_rejected(self):
        with self.assertRaises(ValidationError):
            BeatPlan(
                beats=[
                    _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                    _make_beat("beat_02", 1, 5.0, BeatType.BODY),  # duplicate order
                ]
            )

    def test_missing_order_in_sequence_rejected(self):
        with self.assertRaises(ValidationError):
            BeatPlan(
                beats=[
                    _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                    _make_beat("beat_02", 3, 5.0, BeatType.ENDING),  # gap: no order=2
                ]
            )

    def test_order_not_starting_at_one_rejected(self):
        with self.assertRaises(ValidationError):
            BeatPlan(beats=[_make_beat("beat_01", 2, 4.0, BeatType.HOOK)])

    def test_total_duration_calculated_correctly(self):
        plan = BeatPlan(
            beats=[
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                _make_beat("beat_02", 2, 20.5, BeatType.BUILD),
                _make_beat("beat_03", 3, 5.5, BeatType.ENDING),
            ]
        )
        self.assertEqual(plan.total_duration, 30.0)

    def test_total_duration_cannot_be_set_inconsistently(self):
        # total_duration is a derived @computed_field, not a real input
        # field -- passing one in is silently ignored (BeatPlan tolerates
        # unknown keys precisely so its own JSON output round-trips; see
        # schemas.py), and the real value is always recomputed from beats.
        plan = BeatPlan.model_validate(
            {
                "beats": [{"id": "beat_01", "order": 1, "duration": 4.0, "type": "HOOK"}],
                "total_duration": 9999.0,
            }
        )
        self.assertEqual(plan.total_duration, 4.0)


class BeatSerializationTests(unittest.TestCase):
    def _sample_plan(self) -> BeatPlan:
        return BeatPlan(
            video_id=42,
            script_text="Anna and Tom's story.",
            beats=[
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK, asset_id=101, motion_preset=BeatMotionPreset.SLOW_PUSH_IN),
                _make_beat("beat_02", 2, 20.0, BeatType.BUILD),
                _make_beat("beat_03", 3, 5.0, BeatType.ENDING),
            ],
        )

    def test_serialization_produces_expected_json_shape(self):
        plan = self._sample_plan()
        raw = json.loads(plan.model_dump_json())
        self.assertEqual(raw["video_id"], 42)
        self.assertEqual(raw["total_duration"], 29.0)
        self.assertEqual(len(raw["beats"]), 3)
        first = raw["beats"][0]
        self.assertEqual(first["id"], "beat_01")
        self.assertEqual(first["type"], "HOOK")
        self.assertEqual(first["visual_hint"], "emotional couple, road trip")
        self.assertEqual(first["asset_id"], 101)
        self.assertIsNone(raw["beats"][1]["asset_id"])
        self.assertEqual(first["motion_preset"], "SLOW_PUSH_IN")
        # beats[1] never had an explicit motion_preset in _sample_plan() --
        # None ("inherit the project default"), not "STATIC" (Task 12).
        self.assertIsNone(raw["beats"][1]["motion_preset"])

    def test_deserialization_from_json_reconstructs_equivalent_plan(self):
        plan = self._sample_plan()
        restored = BeatPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)

    def test_json_round_trip_preserves_all_meaningful_information(self):
        plan = self._sample_plan()
        restored = BeatPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)
        self.assertEqual(restored.total_duration, plan.total_duration)
        self.assertEqual([b.id for b in restored.ordered_beats()], [b.id for b in plan.ordered_beats()])

    def test_deserialization_rejects_bad_ordering_from_json(self):
        bad_json = json.dumps(
            {
                "beats": [
                    {"id": "beat_01", "order": 1, "duration": 4.0, "type": "HOOK"},
                    {"id": "beat_02", "order": 1, "duration": 4.0, "type": "BODY"},  # duplicate
                ]
            }
        )
        with self.assertRaises(ValidationError):
            BeatPlan.model_validate_json(bad_json)


class MotionBackwardCompatibilityTests(unittest.TestCase):
    """A beats.json written before this task's motion_preset field existed
    (Tasks 01-04's shape: id/order/type/narration/duration/visual_hint/
    asset_id only) must keep loading with no migration -- see
    docs/features/33-motion-presets-beat-motion-assignment.md.
    """

    def test_old_style_beat_json_without_motion_preset_loads_and_resolves_as_static(self):
        old_style_beat = json.loads(
            json.dumps(
                {
                    "id": "beat_01",
                    "order": 1,
                    "type": "HOOK",
                    "narration": "Meet Anna.",
                    "duration": 4.0,
                    "visual_hint": "a couple",
                    "asset_id": 5,
                }
            )
        )
        beat = Beat.model_validate(old_style_beat)
        self.assertIsNone(beat.motion_preset)
        self.assertEqual(effective_motion_preset(beat, DEFAULT_PROJECT_CONFIG), BeatMotionPreset.STATIC)

    def test_old_style_beat_plan_json_without_any_motion_preset_loads_and_resolves_as_static(self):
        old_style_plan = {
            "beats": [
                {"id": "beat_01", "order": 1, "duration": 4.0, "type": "HOOK"},
                {"id": "beat_02", "order": 2, "duration": 5.0, "type": "BODY"},
            ]
        }
        plan = BeatPlan.model_validate(old_style_plan)
        self.assertTrue(all(beat.motion_preset is None for beat in plan.beats))
        self.assertTrue(
            all(effective_motion_preset(beat, plan.config) == BeatMotionPreset.STATIC for beat in plan.beats)
        )


class DeterminismTests(unittest.TestCase):
    def test_same_input_produces_equivalent_serialized_output(self):
        def build() -> BeatPlan:
            return BeatPlan(
                video_id=7,
                script_text="A short vertical-video script.",
                beats=[
                    _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                    _make_beat("beat_02", 2, 20.0, BeatType.BUILD),
                    _make_beat("beat_03", 3, 5.0, BeatType.ENDING),
                ],
            )

        self.assertEqual(build().model_dump_json(), build().model_dump_json())
        self.assertEqual(build(), build())


class BeatsJsonFileTests(unittest.TestCase):
    def test_save_and_load_round_trip_via_beats_json(self):
        plan = BeatPlan(
            video_id=7,
            script_text="A short vertical-video script.",
            beats=[
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                _make_beat("beat_02", 2, 20.0, BeatType.BUILD),
                _make_beat("beat_03", 3, 5.0, BeatType.REVEAL),
                _make_beat("beat_04", 4, 3.0, BeatType.ENDING),
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            beats_json_path = Path(tmp) / "beats.json"
            save_beats_json(plan, beats_json_path)

            self.assertTrue(beats_json_path.exists())
            restored = load_beats_json(beats_json_path)

            self.assertEqual(restored, plan)
            self.assertEqual(restored.total_duration, 32.0)
            self.assertEqual(
                [b.id for b in restored.ordered_beats()], ["beat_01", "beat_02", "beat_03", "beat_04"]
            )


if __name__ == "__main__":
    unittest.main()
