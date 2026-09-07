"""Tests for app.modules.ai.model_router (AI Storytelling Studio plan,
Phase 0). Pure -- task kind + provider in, routing decision out.
"""

import unittest

from app.modules.ai.model_router import TASK_TIER_MAP, TIERS, route


class RoutingTests(unittest.TestCase):
    def test_known_tasks_route_to_their_mapped_tier(self):
        self.assertEqual(route("classification", "anthropic").tier, "cheap")
        self.assertEqual(route("scene_breakdown", "anthropic").tier, "standard")
        self.assertEqual(route("final_polish", "openai").tier, "premium")

    def test_unknown_task_defaults_to_standard_never_downgrades(self):
        self.assertEqual(route("something_new_the_router_hasnt_heard_of", "anthropic").tier, "standard")

    def test_tier_override_wins_over_the_map(self):
        d = route("classification", "anthropic", tier_override="premium")
        self.assertEqual(d.tier, "premium")

    def test_phase0_model_is_always_none_meaning_provider_default(self):
        # No cheap/premium models configured yet -- every route uses the
        # provider's default model.
        for task in ("classification", "script", "localize_scenes"):
            self.assertIsNone(route(task, "anthropic").model)
            self.assertIsNone(route(task, "openai").model)

    def test_premium_gets_token_headroom_standard_does_not(self):
        self.assertEqual(route("scene_breakdown", "anthropic").max_tokens_bonus, 0)
        self.assertGreater(route("final_polish", "anthropic").max_tokens_bonus, 0)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            route("script", "some-other-vendor")

    def test_every_mapped_tier_is_valid(self):
        for tier in TASK_TIER_MAP.values():
            self.assertIn(tier, TIERS)


if __name__ == "__main__":
    unittest.main()
