import unittest

from pydantic import ValidationError

from app.modules.motion.schemas import MAX_DURATION, MIN_DURATION, MotionIntensity, MotionPlan, MotionPresetName
from app.modules.motion.service import build_motion_plan, list_presets, select_auto_motion


class PresetRegistryTests(unittest.TestCase):
    def test_all_nine_presets_are_registered(self):
        expected = {
            "static",
            "slow_push_in",
            "slow_pull_out",
            "pan_left",
            "pan_right",
            "pan_up",
            "pan_down",
            "zoom_and_pan",
            "subtle_rotate",
        }
        self.assertEqual({preset.value for preset in list_presets()}, expected)

    def test_every_preset_builds_a_valid_motion_plan(self):
        for preset in list_presets():
            plan = build_motion_plan(preset)
            self.assertIsInstance(plan, MotionPlan)
            self.assertEqual(plan.preset, preset)

    def test_static_preset_has_no_movement(self):
        plan = build_motion_plan(MotionPresetName.STATIC)
        self.assertEqual(plan.scale.start, plan.scale.end)
        self.assertEqual(plan.position.x_start, plan.position.x_end)
        self.assertEqual(plan.position.y_start, plan.position.y_end)
        self.assertEqual(plan.rotation.start, plan.rotation.end)

    def test_subtle_rotate_preset_actually_rotates(self):
        plan = build_motion_plan(MotionPresetName.SUBTLE_ROTATE)
        self.assertNotEqual(plan.rotation.start, plan.rotation.end)

    def test_pan_presets_move_position_without_rotating(self):
        for preset in (
            MotionPresetName.PAN_LEFT,
            MotionPresetName.PAN_RIGHT,
            MotionPresetName.PAN_UP,
            MotionPresetName.PAN_DOWN,
        ):
            plan = build_motion_plan(preset)
            moved = (plan.position.x_start, plan.position.y_start) != (plan.position.x_end, plan.position.y_end)
            self.assertTrue(moved, f"{preset} should move position")
            self.assertEqual(plan.rotation.start, plan.rotation.end)

    def test_every_preset_keeps_scale_at_or_above_one(self):
        # Headroom requirement: a pan/rotate must never reveal the source
        # frame's edges (see schemas.py's MIN_SCALE note).
        for preset in list_presets():
            plan = build_motion_plan(preset)
            self.assertGreaterEqual(plan.scale.start, 1.0)
            self.assertGreaterEqual(plan.scale.end, 1.0)


class BuildMotionPlanTests(unittest.TestCase):
    def test_invalid_preset_raises_value_error(self):
        with self.assertRaises(ValueError):
            build_motion_plan("not_a_real_preset")

    def test_invalid_preset_error_lists_valid_options(self):
        with self.assertRaises(ValueError) as ctx:
            build_motion_plan("nonexistent")
        self.assertIn("slow_push_in", str(ctx.exception))

    def test_accepts_preset_as_plain_string(self):
        plan = build_motion_plan("slow_push_in")
        self.assertEqual(plan.preset, MotionPresetName.SLOW_PUSH_IN)

    def test_duration_override_is_applied(self):
        plan = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, duration=6.5)
        self.assertEqual(plan.duration, 6.5)

    def test_omitted_duration_uses_preset_default(self):
        plan = build_motion_plan(MotionPresetName.SLOW_PUSH_IN)
        self.assertEqual(plan.duration, 4.0)

    def test_duration_override_out_of_range_is_rejected(self):
        with self.assertRaises(ValidationError):
            build_motion_plan(MotionPresetName.SLOW_PUSH_IN, duration=MAX_DURATION + 1)
        with self.assertRaises(ValidationError):
            build_motion_plan(MotionPresetName.SLOW_PUSH_IN, duration=MIN_DURATION - 0.05)

    def test_deterministic_output_same_preset_produces_equal_plans(self):
        first = build_motion_plan(MotionPresetName.ZOOM_AND_PAN)
        second = build_motion_plan(MotionPresetName.ZOOM_AND_PAN)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)  # equal by value, not the same object

    def test_deterministic_output_with_duration_override(self):
        first = build_motion_plan(MotionPresetName.PAN_LEFT, duration=7.0)
        second = build_motion_plan(MotionPresetName.PAN_LEFT, duration=7.0)
        self.assertEqual(first, second)

    def test_different_presets_produce_different_plans(self):
        push_in = build_motion_plan(MotionPresetName.SLOW_PUSH_IN)
        pull_out = build_motion_plan(MotionPresetName.SLOW_PULL_OUT)
        self.assertNotEqual(push_in, pull_out)

    def test_build_motion_plan_output_round_trips_through_json(self):
        plan = build_motion_plan(MotionPresetName.ZOOM_AND_PAN, duration=5.0)
        restored = MotionPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(restored, plan)


class IntensityTests(unittest.TestCase):
    def test_medium_intensity_matches_original_hardcoded_numbers(self):
        # Backward-compatibility guarantee (Task 23 -- see
        # docs/features/49-local-motion-engine.md section 26): MEDIUM +
        # center focal must be byte-identical to this module's own
        # pre-Task-23 preset numbers.
        plan = build_motion_plan(MotionPresetName.PAN_LEFT, intensity=MotionIntensity.MEDIUM)
        self.assertEqual(plan.scale.start, 1.15)
        self.assertEqual(plan.position.x_start, 0.6)
        self.assertEqual(plan.position.x_end, 0.4)

    def test_subtle_produces_a_smaller_delta_than_medium(self):
        medium = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, intensity=MotionIntensity.MEDIUM)
        subtle = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, intensity=MotionIntensity.SUBTLE)
        self.assertLess(subtle.scale.end - 1.0, medium.scale.end - 1.0)

    def test_strong_produces_a_larger_delta_than_medium(self):
        medium = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, intensity=MotionIntensity.MEDIUM)
        strong = build_motion_plan(MotionPresetName.SLOW_PUSH_IN, intensity=MotionIntensity.STRONG)
        self.assertGreater(strong.scale.end - 1.0, medium.scale.end - 1.0)

    def test_intensity_accepts_plain_string(self):
        plan = build_motion_plan(MotionPresetName.PAN_LEFT, intensity="STRONG")
        self.assertGreater(plan.scale.start, 1.15)

    def test_unknown_intensity_raises_value_error(self):
        with self.assertRaises(ValueError):
            build_motion_plan(MotionPresetName.PAN_LEFT, intensity="EXTREME")

    def test_static_preset_is_unaffected_by_intensity(self):
        subtle = build_motion_plan(MotionPresetName.STATIC, intensity=MotionIntensity.SUBTLE)
        strong = build_motion_plan(MotionPresetName.STATIC, intensity=MotionIntensity.STRONG)
        self.assertEqual(subtle, strong)

    def test_scale_and_position_stay_within_documented_bounds_at_strong(self):
        for preset in list_presets():
            plan = build_motion_plan(preset, intensity=MotionIntensity.STRONG, focal_x=0.95, focal_y=0.05)
            self.assertGreaterEqual(plan.scale.start, 1.0)
            self.assertLessEqual(plan.scale.start, 4.0)
            self.assertGreaterEqual(plan.scale.end, 1.0)
            self.assertLessEqual(plan.scale.end, 4.0)
            for value in (plan.position.x_start, plan.position.y_start, plan.position.x_end, plan.position.y_end):
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)


class FocalPointTests(unittest.TestCase):
    def test_pan_preset_pivots_around_the_given_focal_point(self):
        plan = build_motion_plan(MotionPresetName.PAN_LEFT, focal_x=0.8, focal_y=0.3)
        self.assertAlmostEqual(plan.position.y_start, 0.3)
        self.assertAlmostEqual(plan.position.y_end, 0.3)
        # PAN_LEFT's own shape (start > end on x) is preserved around the
        # new pivot, not collapsed to a fixed absolute position.
        self.assertGreater(plan.position.x_start, plan.position.x_end)

    def test_default_focal_point_is_frame_center(self):
        explicit_center = build_motion_plan(MotionPresetName.ZOOM_AND_PAN, focal_x=0.5, focal_y=0.5)
        default = build_motion_plan(MotionPresetName.ZOOM_AND_PAN)
        self.assertEqual(explicit_center, default)

    def test_focal_point_near_edge_is_clamped_not_out_of_bounds(self):
        plan = build_motion_plan(MotionPresetName.PAN_RIGHT, focal_x=0.98, intensity=MotionIntensity.STRONG)
        self.assertLessEqual(plan.position.x_start, 1.0)
        self.assertLessEqual(plan.position.x_end, 1.0)
        self.assertGreaterEqual(plan.position.x_start, 0.0)
        self.assertGreaterEqual(plan.position.x_end, 0.0)


class AutoMotionSelectionTests(unittest.TestCase):
    def test_same_beat_order_and_hint_always_selects_the_same_preset(self):
        first = select_auto_motion(3, "a quiet moment")
        second = select_auto_motion(3, "a quiet moment")
        self.assertEqual(first, second)

    def test_emotional_keyword_selects_push_in(self):
        self.assertEqual(select_auto_motion(5, "an emotional, intimate close-up"), MotionPresetName.SLOW_PUSH_IN)

    def test_wide_establishing_keyword_selects_pull_out(self):
        self.assertEqual(select_auto_motion(5, "a wide establishing shot of the skyline"), MotionPresetName.SLOW_PULL_OUT)

    def test_static_information_keyword_selects_static(self):
        self.assertEqual(select_auto_motion(5, "a static chart with information"), MotionPresetName.STATIC)

    def test_no_keyword_match_falls_back_to_beat_order_rotation(self):
        # Section 29's own worked example -- consecutive beats with no
        # visual-intent match cycle through different presets, never the
        # same one repeated ("every beat = zoom in").
        selections = [select_auto_motion(i, None) for i in range(1, 8)]
        self.assertEqual(len(set(selections)), len(selections))  # all 7 distinct within one full rotation

    def test_rotation_wraps_around_after_a_full_cycle(self):
        first_cycle = [select_auto_motion(i, None) for i in range(1, 8)]
        second_cycle = [select_auto_motion(i, None) for i in range(8, 15)]
        self.assertEqual(first_cycle, second_cycle)

    def test_blank_hint_does_not_match_any_keyword_rule(self):
        # An empty/whitespace-only hint must fall through to the rotation,
        # not accidentally match a keyword via a substring of "".
        result = select_auto_motion(1, "   ")
        self.assertEqual(result, select_auto_motion(1, None))


if __name__ == "__main__":
    unittest.main()
