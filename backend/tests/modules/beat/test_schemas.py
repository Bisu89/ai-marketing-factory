import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.modules.beat.schemas import (
    AudioConfig,
    Beat,
    BeatPlan,
    BeatType,
    CaptionConfig,
    MotionConfig,
    VisualRequirement,
)
from app.modules.beat.service import load_beats_json, save_beats_json


def _make_beat(id_: str = "beat_01", order: int = 1, duration: float = 4.0, type_: BeatType = BeatType.HOOK) -> Beat:
    return Beat(
        id=id_,
        order=order,
        duration=duration,
        type=type_,
        narration="Meet Anna and Tom.",
        visual=VisualRequirement(asset_query=["couple", "emotional"], asset_id=None),
        motion=MotionConfig(preset="slow_push_in"),
        caption=CaptionConfig(text="Meet Anna and Tom.", preset="emotional"),
        audio=AudioConfig(sfx=None),
    )


class BeatValidationTests(unittest.TestCase):
    def test_valid_beat(self):
        beat = _make_beat()
        self.assertEqual(beat.id, "beat_01")
        self.assertEqual(beat.order, 1)
        self.assertEqual(beat.duration, 4.0)
        self.assertEqual(beat.type, BeatType.HOOK)
        self.assertEqual(beat.visual.asset_query, ["couple", "emotional"])
        self.assertEqual(beat.motion.preset, "slow_push_in")

    def test_invalid_duration_zero_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(duration=0.0)

    def test_invalid_duration_negative_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(duration=-2.0)

    def test_invalid_order_below_one_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(order=0)

    def test_blank_id_rejected(self):
        with self.assertRaises(ValidationError):
            _make_beat(id_="   ")


class BeatPlanOrderingTests(unittest.TestCase):
    def test_multiple_beats_valid_sequence(self):
        plan = BeatPlan(
            beats=[
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                _make_beat("beat_02", 2, 20.0, BeatType.BODY),
                _make_beat("beat_03", 3, 5.0, BeatType.CTA),
            ]
        )
        self.assertEqual(len(plan.beats), 3)
        self.assertEqual([b.id for b in plan.ordered_beats()], ["beat_01", "beat_02", "beat_03"])

    def test_invalid_ordering_gap_rejected(self):
        with self.assertRaises(ValidationError):
            BeatPlan(
                beats=[
                    _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                    _make_beat("beat_02", 3, 5.0, BeatType.CTA),  # gap: no order=2
                ]
            )

    def test_invalid_ordering_duplicate_rejected(self):
        with self.assertRaises(ValidationError):
            BeatPlan(
                beats=[
                    _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                    _make_beat("beat_02", 1, 5.0, BeatType.CTA),  # duplicate order
                ]
            )

    def test_invalid_ordering_not_starting_at_one_rejected(self):
        with self.assertRaises(ValidationError):
            BeatPlan(beats=[_make_beat("beat_01", 2, 4.0, BeatType.HOOK)])

    def test_out_of_list_order_input_still_validates_by_order_field(self):
        # Beats can arrive out of list order; ordering validation looks at
        # the `order` field's values, not list position.
        plan = BeatPlan(
            beats=[
                _make_beat("beat_02", 2, 5.0, BeatType.BODY),
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
            ]
        )
        self.assertEqual([b.id for b in plan.ordered_beats()], ["beat_01", "beat_02"])

    def test_total_duration(self):
        plan = BeatPlan(
            beats=[
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                _make_beat("beat_02", 2, 20.5, BeatType.BODY),
                _make_beat("beat_03", 3, 5.5, BeatType.CTA),
            ]
        )
        self.assertEqual(plan.total_duration, 30.0)

    def test_empty_plan_is_valid_with_zero_duration(self):
        plan = BeatPlan()
        self.assertEqual(plan.beats, [])
        self.assertEqual(plan.total_duration, 0.0)


class BeatSerializationTests(unittest.TestCase):
    def _sample_plan(self) -> BeatPlan:
        return BeatPlan(
            video_id=42,
            script_text="Anna and Tom's story.",
            beats=[
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                _make_beat("beat_02", 2, 20.0, BeatType.BODY),
                _make_beat("beat_03", 3, 5.0, BeatType.CTA),
            ],
        )

    def test_serialization_produces_expected_json_shape(self):
        plan = self._sample_plan()
        raw = json.loads(plan.model_dump_json())
        self.assertEqual(raw["video_id"], 42)
        self.assertEqual(len(raw["beats"]), 3)
        first = raw["beats"][0]
        self.assertEqual(first["id"], "beat_01")
        self.assertEqual(first["type"], "hook")
        self.assertEqual(first["visual"]["asset_query"], ["couple", "emotional"])
        self.assertEqual(first["motion"]["preset"], "slow_push_in")

    def test_deserialization_round_trip_preserves_data(self):
        plan = self._sample_plan()
        restored = BeatPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)
        self.assertEqual(restored.total_duration, plan.total_duration)

    def test_deserialization_rejects_bad_ordering_from_json(self):
        bad_json = json.dumps(
            {
                "beats": [
                    {"id": "beat_01", "order": 1, "duration": 4.0, "type": "hook", "narration": ""},
                    {"id": "beat_02", "order": 1, "duration": 4.0, "type": "body", "narration": ""},  # duplicate
                ]
            }
        )
        with self.assertRaises(ValidationError):
            BeatPlan.model_validate_json(bad_json)


class BeatsJsonFileTests(unittest.TestCase):
    def test_save_and_load_round_trip_via_beats_json(self):
        plan = BeatPlan(
            video_id=7,
            script_text="A short vertical-video script.",
            beats=[
                _make_beat("beat_01", 1, 4.0, BeatType.HOOK),
                _make_beat("beat_02", 2, 20.0, BeatType.BODY),
                _make_beat("beat_03", 3, 5.0, BeatType.CTA),
                _make_beat("beat_04", 4, 3.0, BeatType.OUTRO),
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
