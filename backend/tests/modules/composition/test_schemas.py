import json
import unittest

from pydantic import ValidationError

from app.modules.composition.schemas import (
    CompositionPlan,
    Easing,
    OutputFormat,
    PositionRange,
    RotationRange,
    ScaleRange,
    Scene,
    SceneAudio,
    SceneCaption,
    SceneMotion,
    SceneTransition,
    TransitionType,
)


def _motion(**overrides) -> SceneMotion:
    data = dict(
        preset_name="slow_push_in",
        scale=ScaleRange(start=1.0, end=1.08),
        position=PositionRange(x_start=0.5, y_start=0.5, x_end=0.52, y_end=0.48),
        rotation=RotationRange(start=0.0, end=0.0),
        easing=Easing.EASE_IN_OUT,
    )
    data.update(overrides)
    return SceneMotion(**data)


def _output_format(**overrides) -> OutputFormat:
    data = dict(width=1080, height=1920, fps=30.0)
    data.update(overrides)
    return OutputFormat(**data)


def _scene(**overrides) -> Scene:
    data = dict(
        id="scene_01",
        order=1,
        beat_id="beat_01",
        duration=4.0,
        source_asset_id=42,
        motion=_motion(),
        caption=SceneCaption(text="Meet Anna and Tom.", preset="emotional"),
        audio=SceneAudio(sfx=None),
        transition=SceneTransition(type=TransitionType.CUT, duration=0.0),
        output_format=_output_format(),
    )
    data.update(overrides)
    return Scene(**data)


class SceneMotionValidationTests(unittest.TestCase):
    def test_valid_motion(self):
        motion = _motion()
        self.assertEqual(motion.scale.start, 1.0)
        self.assertEqual(motion.easing, Easing.EASE_IN_OUT)

    def test_invalid_scale_below_minimum_rejected(self):
        with self.assertRaises(ValidationError):
            _motion(scale=ScaleRange(start=0.5, end=1.0))

    def test_invalid_scale_above_maximum_rejected(self):
        with self.assertRaises(ValidationError):
            _motion(scale=ScaleRange(start=1.0, end=10.0))

    def test_invalid_position_out_of_frame_rejected(self):
        with self.assertRaises(ValidationError):
            _motion(position=PositionRange(x_start=1.5, y_start=0.5, x_end=0.5, y_end=0.5))

    def test_invalid_rotation_beyond_bound_rejected(self):
        with self.assertRaises(ValidationError):
            _motion(rotation=RotationRange(start=-45.0, end=45.0))

    def test_unrecognized_preset_name_is_not_rejected(self):
        # preset_name is a free-form traceability label, not validated
        # against Motion's own preset taxonomy (see schemas.py docstring).
        motion = _motion(preset_name="some_future_preset_this_contract_has_never_heard_of")
        self.assertEqual(motion.preset_name, "some_future_preset_this_contract_has_never_heard_of")


class SceneValidationTests(unittest.TestCase):
    def test_valid_scene(self):
        scene = _scene()
        self.assertEqual(scene.id, "scene_01")
        self.assertEqual(scene.order, 1)
        self.assertEqual(scene.source_asset_id, 42)
        self.assertEqual(scene.duration, 4.0)

    def test_composition_creation_with_full_scene_fields(self):
        scene = _scene()
        self.assertEqual(scene.caption.text, "Meet Anna and Tom.")
        self.assertEqual(scene.transition.type, TransitionType.CUT)
        self.assertEqual(scene.output_format.width, 1080)

    def test_missing_asset_field_omitted_is_rejected(self):
        with self.assertRaises(ValidationError):
            Scene(
                id="scene_01",
                order=1,
                duration=4.0,
                motion=_motion(),
                output_format=_output_format(),
            )

    def test_missing_asset_zero_id_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(source_asset_id=0)

    def test_missing_asset_negative_id_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(source_asset_id=-1)

    def test_invalid_motion_embedded_in_scene_is_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(motion=_motion(scale=ScaleRange(start=0.2, end=0.5)))

    def test_invalid_duration_zero_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(duration=0.0)

    def test_invalid_duration_negative_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(duration=-1.0)

    def test_invalid_order_below_one_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(order=0)

    def test_blank_id_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(id="   ")

    def test_invalid_transition_duration_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(transition=SceneTransition(type=TransitionType.CROSSFADE, duration=99.0))

    def test_invalid_output_format_rejected(self):
        with self.assertRaises(ValidationError):
            _scene(output_format=_output_format(width=0))


class CompositionPlanOrderingAndDurationTests(unittest.TestCase):
    def test_multiple_scenes_valid_sequence(self):
        plan = CompositionPlan(
            scenes=[
                _scene(id="scene_01", order=1, duration=4.0),
                _scene(id="scene_02", order=2, duration=20.0),
                _scene(id="scene_03", order=3, duration=5.0),
            ]
        )
        self.assertEqual(len(plan.scenes), 3)
        self.assertEqual([s.id for s in plan.ordered_scenes()], ["scene_01", "scene_02", "scene_03"])

    def test_scene_ordering_gap_rejected(self):
        with self.assertRaises(ValidationError):
            CompositionPlan(
                scenes=[
                    _scene(id="scene_01", order=1),
                    _scene(id="scene_02", order=3),  # gap: no order=2
                ]
            )

    def test_scene_ordering_duplicate_rejected(self):
        with self.assertRaises(ValidationError):
            CompositionPlan(
                scenes=[
                    _scene(id="scene_01", order=1),
                    _scene(id="scene_02", order=1),  # duplicate
                ]
            )

    def test_scenes_out_of_list_order_still_validate_by_order_field(self):
        plan = CompositionPlan(
            scenes=[
                _scene(id="scene_02", order=2),
                _scene(id="scene_01", order=1),
            ]
        )
        self.assertEqual([s.id for s in plan.ordered_scenes()], ["scene_01", "scene_02"])

    def test_duration_calculation_sums_scene_durations(self):
        plan = CompositionPlan(
            scenes=[
                _scene(id="scene_01", order=1, duration=4.0),
                _scene(id="scene_02", order=2, duration=20.5),
                _scene(id="scene_03", order=3, duration=5.5),
            ]
        )
        self.assertEqual(plan.total_duration, 30.0)

    def test_empty_plan_is_valid_with_zero_duration(self):
        plan = CompositionPlan()
        self.assertEqual(plan.scenes, [])
        self.assertEqual(plan.total_duration, 0.0)


class CompositionPlanSerializationTests(unittest.TestCase):
    def _sample_plan(self) -> CompositionPlan:
        return CompositionPlan(
            video_id=42,
            narration_script="Anna and Tom's story.",
            voice="en-US-GuyNeural",
            language="english",
            scenes=[
                _scene(id="scene_01", order=1, duration=4.0),
                _scene(id="scene_02", order=2, duration=20.0),
            ],
        )

    def test_serialization_produces_expected_json_shape(self):
        plan = self._sample_plan()
        raw = json.loads(plan.model_dump_json())
        self.assertEqual(raw["video_id"], 42)
        self.assertEqual(len(raw["scenes"]), 2)
        first = raw["scenes"][0]
        self.assertEqual(first["id"], "scene_01")
        self.assertEqual(first["source_asset_id"], 42)
        self.assertEqual(first["motion"]["scale"], {"start": 1.0, "end": 1.08})
        self.assertEqual(first["transition"]["type"], "cut")
        self.assertEqual(first["output_format"], {"width": 1080, "height": 1920, "fps": 30.0})

    def test_deserialization_round_trip_is_reproducible(self):
        plan = self._sample_plan()
        restored = CompositionPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)
        self.assertEqual(restored.total_duration, plan.total_duration)

    def test_deserialization_rejects_bad_ordering_from_json(self):
        bad_json = json.dumps(
            {
                "scenes": [
                    {
                        "id": "scene_01",
                        "order": 1,
                        "duration": 4.0,
                        "source_asset_id": 1,
                        "motion": {
                            "scale": {"start": 1.0, "end": 1.0},
                            "position": {"x_start": 0.5, "y_start": 0.5, "x_end": 0.5, "y_end": 0.5},
                        },
                        "output_format": {"width": 1080, "height": 1920},
                    },
                    {
                        "id": "scene_02",
                        "order": 1,  # duplicate
                        "duration": 4.0,
                        "source_asset_id": 2,
                        "motion": {
                            "scale": {"start": 1.0, "end": 1.0},
                            "position": {"x_start": 0.5, "y_start": 0.5, "x_end": 0.5, "y_end": 0.5},
                        },
                        "output_format": {"width": 1080, "height": 1920},
                    },
                ]
            }
        )
        with self.assertRaises(ValidationError):
            CompositionPlan.model_validate_json(bad_json)

    def test_deserialization_rejects_missing_asset_from_json(self):
        bad_json = json.dumps(
            {
                "scenes": [
                    {
                        "id": "scene_01",
                        "order": 1,
                        "duration": 4.0,
                        # source_asset_id omitted entirely -- missing asset
                        "motion": {
                            "scale": {"start": 1.0, "end": 1.0},
                            "position": {"x_start": 0.5, "y_start": 0.5, "x_end": 0.5, "y_end": 0.5},
                        },
                        "output_format": {"width": 1080, "height": 1920},
                    }
                ]
            }
        )
        with self.assertRaises(ValidationError):
            CompositionPlan.model_validate_json(bad_json)


if __name__ == "__main__":
    unittest.main()
