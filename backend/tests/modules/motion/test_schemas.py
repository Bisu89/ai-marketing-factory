import json
import unittest

from pydantic import ValidationError

from app.modules.motion.schemas import (
    Easing,
    MotionPlan,
    MotionPresetName,
    PositionRange,
    RotationRange,
    ScaleRange,
)


def _valid_plan(**overrides) -> MotionPlan:
    data = dict(
        preset=MotionPresetName.SLOW_PUSH_IN,
        duration=4.0,
        scale=ScaleRange(start=1.0, end=1.08),
        position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.52, y_end=0.48),
        rotation=RotationRange(start=0.0, end=0.0),
        easing=Easing.EASE_IN_OUT,
    )
    data.update(overrides)
    return MotionPlan(**data)


class ScaleRangeTests(unittest.TestCase):
    def test_valid_scale(self):
        scale = ScaleRange(start=1.0, end=1.08)
        self.assertEqual(scale.start, 1.0)
        self.assertEqual(scale.end, 1.08)

    def test_scale_below_minimum_rejected(self):
        with self.assertRaises(ValidationError):
            ScaleRange(start=0.9, end=1.0)

    def test_scale_above_maximum_rejected(self):
        with self.assertRaises(ValidationError):
            ScaleRange(start=1.0, end=10.0)


class PositionRangeTests(unittest.TestCase):
    def test_valid_position(self):
        position = PositionRange(x_start=0.5, y_start=0.5, x_end=0.6, y_end=0.4)
        self.assertEqual(position.x_end, 0.6)

    def test_position_below_zero_rejected(self):
        with self.assertRaises(ValidationError):
            PositionRange(x_start=-0.1, y_start=0.5, x_end=0.5, y_end=0.5)

    def test_position_above_one_rejected(self):
        with self.assertRaises(ValidationError):
            PositionRange(x_start=0.5, y_start=1.5, x_end=0.5, y_end=0.5)


class RotationRangeTests(unittest.TestCase):
    def test_default_rotation_is_zero(self):
        rotation = RotationRange()
        self.assertEqual(rotation.start, 0.0)
        self.assertEqual(rotation.end, 0.0)

    def test_subtle_rotation_within_bounds_accepted(self):
        rotation = RotationRange(start=-3.0, end=3.0)
        self.assertEqual(rotation.start, -3.0)

    def test_rotation_beyond_bound_rejected(self):
        with self.assertRaises(ValidationError):
            RotationRange(start=-45.0, end=45.0)


class MotionPlanValidationTests(unittest.TestCase):
    def test_valid_plan(self):
        plan = _valid_plan()
        self.assertEqual(plan.preset, MotionPresetName.SLOW_PUSH_IN)
        self.assertEqual(plan.duration, 4.0)
        self.assertEqual(plan.easing, Easing.EASE_IN_OUT)

    def test_invalid_duration_zero_rejected(self):
        with self.assertRaises(ValidationError):
            _valid_plan(duration=0.0)

    def test_invalid_duration_negative_rejected(self):
        with self.assertRaises(ValidationError):
            _valid_plan(duration=-2.0)

    def test_invalid_duration_too_long_rejected(self):
        with self.assertRaises(ValidationError):
            _valid_plan(duration=999.0)

    def test_invalid_preset_string_rejected(self):
        with self.assertRaises(ValidationError):
            _valid_plan(preset="not_a_real_preset")

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValidationError):
            MotionPlan(
                preset=MotionPresetName.STATIC,
                duration=4.0,
                scale=ScaleRange(start=1.0, end=1.0),
                position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.5, y_end=0.5),
                unexpected_field="nope",
            )

    def test_default_rotation_and_easing_applied_when_omitted(self):
        plan = MotionPlan(
            preset=MotionPresetName.STATIC,
            duration=4.0,
            scale=ScaleRange(start=1.0, end=1.0),
            position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.5, y_end=0.5),
        )
        self.assertEqual(plan.rotation, RotationRange(start=0.0, end=0.0))
        self.assertEqual(plan.easing, Easing.EASE_IN_OUT)


class MotionPlanSerializationTests(unittest.TestCase):
    def test_serialization_produces_expected_json_shape(self):
        plan = _valid_plan()
        raw = json.loads(plan.model_dump_json())
        self.assertEqual(raw["preset"], "slow_push_in")
        self.assertEqual(raw["duration"], 4.0)
        self.assertEqual(raw["scale"], {"start": 1.0, "end": 1.08})
        self.assertEqual(raw["position"], {"x_start": 0.5, "y_start": 0.5, "x_end": 0.52, "y_end": 0.48})
        self.assertEqual(raw["easing"], "ease_in_out")

    def test_deserialization_round_trip_preserves_data(self):
        plan = _valid_plan()
        restored = MotionPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)

    def test_deserialization_rejects_invalid_json_payload(self):
        bad_json = json.dumps(
            {
                "preset": "slow_push_in",
                "duration": -1.0,
                "scale": {"start": 1.0, "end": 1.08},
                "position": {"x_start": 0.5, "y_start": 0.5, "x_end": 0.52, "y_end": 0.48},
            }
        )
        with self.assertRaises(ValidationError):
            MotionPlan.model_validate_json(bad_json)


if __name__ == "__main__":
    unittest.main()
