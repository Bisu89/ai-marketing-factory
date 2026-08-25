"""Tests for the Beat-generation adapter (app/api/v1/endpoints/beat_generate.py):
LLM response -> parse -> validate against BeatPlan -> bounded repair retry on
validation failure. The AI provider client is always mocked -- these tests
never call a real AI provider (see app.modules.ai.llm_client.call_structured,
patched below).
"""

import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError as PydanticValidationError

from app.api.v1.endpoints.beat_generate import (
    BeatGenerateIn,
    _merge_short_beats,
    generate_beat_plan,
)
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import AICredentials, LLMCallResult
from app.modules.beat.schemas import BeatPlan, BeatType

FAKE_CREDENTIALS = AICredentials(provider="anthropic", api_key="fake-api-key")


def _fake_result(text: str, refused: bool = False) -> LLMCallResult:
    return LLMCallResult(
        text=text, refused=refused, provider="anthropic", model="claude-sonnet-5",
        input_tokens=None, output_tokens=None, latency_ms=10,
    )


VALID_BEATS_JSON = json.dumps(
    {
        "beats": [
            {"type": "HOOK", "narration": "She thought he forgot.", "duration": 4.0, "visual_hint": "woman waiting alone"},
            {"type": "SETUP", "narration": "She waited all evening.", "duration": 3.0, "visual_hint": "clock ticking, empty room"},
            {"type": "REVEAL", "narration": "Then she heard the front door open.", "duration": 3.5, "visual_hint": "door opening, light spilling in"},
            {"type": "REACTION", "narration": "He walked in carrying flowers.", "duration": 4.0, "visual_hint": "man holding flowers and a box"},
            {"type": "ENDING", "narration": "She started crying, overwhelmed.", "duration": 4.5, "visual_hint": "woman crying, smiling"},
        ]
    }
)

# Story-to-Scene Analysis (docs/features/103-story-to-scene-analysis.md)
# validates that concatenated beat narration reproduces the input script
# word-for-word -- this is that same script, so VALID_BEATS_JSON's response
# passes validation when used against it.
VALID_SCRIPT = (
    "She thought he forgot. She waited all evening. Then she heard the front door open. "
    "He walked in carrying flowers. She started crying, overwhelmed."
)


class BeatGenerateInTests(unittest.TestCase):
    def test_valid_script_accepted(self):
        payload = BeatGenerateIn(script="A short narration script.")
        self.assertEqual(payload.script, "A short narration script.")

    def test_empty_script_rejected(self):
        with self.assertRaises(PydanticValidationError):
            BeatGenerateIn(script="")

    def test_whitespace_only_script_rejected(self):
        with self.assertRaises(PydanticValidationError):
            BeatGenerateIn(script="   \n  ")


class GenerateBeatPlanTests(unittest.TestCase):
    def test_missing_api_key_rejected(self):
        with self.assertRaises(ValidationError):
            generate_beat_plan(None, "She waited all evening.")

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_valid_ai_response_becomes_a_valid_beat_plan(self, mock_call):
        mock_call.return_value = _fake_result(VALID_BEATS_JSON)

        plan = generate_beat_plan(FAKE_CREDENTIALS, VALID_SCRIPT)

        self.assertIsInstance(plan, BeatPlan)
        self.assertEqual(len(plan.beats), 5)
        self.assertEqual(plan.beats[0].id, "beat_01")
        self.assertEqual(plan.beats[0].order, 1)
        self.assertEqual(plan.beats[0].type, BeatType.HOOK)
        self.assertEqual(plan.total_duration, 19.0)
        mock_call.assert_called_once()

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_generated_beats_only_use_supported_types(self, mock_call):
        mock_call.return_value = _fake_result(VALID_BEATS_JSON)

        plan = generate_beat_plan(FAKE_CREDENTIALS, VALID_SCRIPT)

        for beat in plan.beats:
            self.assertIn(beat.type, list(BeatType))

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_ai_refusal_raises_external_service_error_without_retry(self, mock_call):
        mock_call.return_value = _fake_result("", refused=True)

        with self.assertRaises(ExternalServiceError):
            generate_beat_plan(FAKE_CREDENTIALS, "A story script.")

        mock_call.assert_called_once()  # refusal is not retried

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_malformed_json_triggers_one_repair_retry_then_succeeds(self, mock_call):
        mock_call.side_effect = [_fake_result("not valid json{{{"), _fake_result(VALID_BEATS_JSON)]

        plan = generate_beat_plan(FAKE_CREDENTIALS, VALID_SCRIPT)

        self.assertEqual(len(plan.beats), 5)
        self.assertEqual(mock_call.call_count, 2)
        # the repair attempt's system prompt must mention the earlier failure
        retry_system_prompt = mock_call.call_args_list[1].kwargs["system"]
        self.assertIn("previous response was invalid", retry_system_prompt)

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_invalid_duration_in_ai_response_is_rejected_by_beat_domain_validation(self, mock_call):
        bad_json = json.dumps(
            {"beats": [{"type": "HOOK", "narration": "x", "duration": -5.0, "visual_hint": "y"}]}
        )
        mock_call.return_value = _fake_result(bad_json)

        with self.assertRaises(ExternalServiceError):
            generate_beat_plan(FAKE_CREDENTIALS, "A story script.")

        self.assertEqual(mock_call.call_count, 2)  # initial + 1 bounded retry, both invalid

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_invalid_type_in_ai_response_is_rejected(self, mock_call):
        bad_json = json.dumps(
            {"beats": [{"type": "NOT_A_REAL_TYPE", "narration": "x", "duration": 3.0, "visual_hint": "y"}]}
        )
        mock_call.return_value = _fake_result(bad_json)

        with self.assertRaises(ExternalServiceError):
            generate_beat_plan(FAKE_CREDENTIALS, "A story script.")

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_empty_beats_array_is_rejected(self, mock_call):
        mock_call.return_value = _fake_result(json.dumps({"beats": []}))

        with self.assertRaises(ExternalServiceError):
            generate_beat_plan(FAKE_CREDENTIALS, "A story script.")

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_exhausted_retries_raise_external_service_error(self, mock_call):
        mock_call.return_value = _fake_result("still not valid json{{{")

        with self.assertRaises(ExternalServiceError):
            generate_beat_plan(FAKE_CREDENTIALS, "A story script.")

        self.assertEqual(mock_call.call_count, 2)


class MergeShortBeatsTests(unittest.TestCase):
    """Real user report: two adjacent short beats (3.1s + 2.0s) each got
    their own separately-billed AI-generated image for no visual benefit.
    """

    def _beat(self, narration: str, duration: float, visual_hint: str = "a shot", type_: str = "BODY") -> dict:
        return {"type": type_, "narration": narration, "duration": duration, "visual_hint": visual_hint}

    def test_two_adjacent_short_beats_merge_into_one(self):
        beats = [
            self._beat("Opening line.", 4.0),
            self._beat("Middle setup.", 4.0),
            self._beat("A short bit.", 3.1),
            self._beat("Another short bit.", 2.0),
            self._beat("Closing line.", 4.5),
        ]

        merged = _merge_short_beats(beats)

        self.assertEqual(len(merged), 4)
        self.assertEqual(merged[2]["narration"], "A short bit. Another short bit.")
        self.assertAlmostEqual(merged[2]["duration"], 5.1)

    def test_no_merge_when_every_beat_is_already_long_enough(self):
        beats = [self._beat(f"Line {i}.", 4.0) for i in range(5)]
        merged = _merge_short_beats(beats)
        self.assertEqual(merged, beats)

    def test_short_opening_beat_is_never_merged_forward(self):
        beats = [
            self._beat("Hook!", 1.5, type_="HOOK"),
            self._beat("Setup line.", 4.0),
            self._beat("Reveal line.", 4.0),
            self._beat("Ending line.", 4.0),
        ]
        merged = _merge_short_beats(beats)
        # Nothing precedes the first beat to fold it into -- left as-is.
        self.assertEqual(len(merged), 4)
        self.assertEqual(merged[0]["narration"], "Hook!")

    def test_never_merges_below_the_minimum_total_beat_count(self):
        # 4 beats, all short enough to want merging -- but collapsing all
        # the way down to 1-2 beats is worse than leaving them alone.
        beats = [self._beat(f"Bit {i}.", 1.0) for i in range(4)]
        merged = _merge_short_beats(beats)
        self.assertEqual(merged, beats)

    def test_does_not_merge_past_the_max_combined_duration(self):
        beats = [
            self._beat("Long opener.", 4.0),
            self._beat("Long middle.", 4.0),
            self._beat("Already long enough on its own.", 8.0),
            self._beat("A short trailing bit.", 2.0),
            self._beat("Closer.", 4.0),
        ]
        # 8.0 + 2.0 = 10.0 exceeds the max merged duration -- left separate.
        merged = _merge_short_beats(beats)
        self.assertEqual(len(merged), 5)

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_generate_beat_plan_merges_the_ai_response_end_to_end(self, mock_call):
        raw = {
            "beats": [
                {"type": "HOOK", "narration": "She thought he forgot.", "duration": 4.0, "visual_hint": "woman waiting alone"},
                {"type": "SETUP", "narration": "She waited all evening.", "duration": 4.0, "visual_hint": "clock ticking"},
                {"type": "REVEAL", "narration": "A short bit.", "duration": 3.1, "visual_hint": "door opening"},
                {"type": "REACTION", "narration": "Another short bit.", "duration": 2.0, "visual_hint": "man in doorway"},
                {"type": "ENDING", "narration": "She started crying.", "duration": 4.5, "visual_hint": "woman crying"},
            ]
        }
        mock_call.return_value = _fake_result(json.dumps(raw))
        script = (
            "She thought he forgot. She waited all evening. A short bit. Another short bit. "
            "She started crying."
        )

        plan = generate_beat_plan(FAKE_CREDENTIALS, script)

        self.assertEqual(len(plan.beats), 4)
        self.assertEqual(plan.beats[2].narration, "A short bit. Another short bit.")
        self.assertAlmostEqual(plan.beats[2].duration, 5.1)
        # id/order stay purely mechanical post-merge, per _beats_from_raw's
        # own contract -- never inherited from the pre-merge index.
        self.assertEqual(plan.beats[2].id, "beat_03")
        self.assertEqual(plan.beats[3].id, "beat_04")


class StoryToSceneAnalysisTests(unittest.TestCase):
    """docs/features/103-story-to-scene-analysis.md -- the new structured
    scene fields, the strict verbatim-narration guarantee, and threading
    idea/character/tone/style/target_duration into the prompt.
    """

    def _beats_json(self, narrations: list[str]) -> str:
        return json.dumps(
            {
                "beats": [
                    {
                        "type": "BODY", "narration": text, "duration": 4.0, "visual_hint": "a shot",
                        "visual_description": "a detailed cinematic description",
                        "location": "a room", "time_of_day": "morning", "emotion": "hopeful",
                        "camera": "medium shot", "lighting": "soft natural light",
                        "continuity_notes": "same room as before",
                    }
                    for text in narrations
                ]
            }
        )

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_richer_scene_fields_land_on_the_beat(self, mock_call):
        mock_call.return_value = _fake_result(self._beats_json(["A story about change."]))

        plan = generate_beat_plan(FAKE_CREDENTIALS, "A story about change.")

        beat = plan.beats[0]
        self.assertEqual(beat.visual_description, "a detailed cinematic description")
        self.assertEqual(beat.location, "a room")
        self.assertEqual(beat.time_of_day, "morning")
        self.assertEqual(beat.emotion, "hopeful")
        self.assertEqual(beat.camera, "medium shot")
        self.assertEqual(beat.lighting, "soft natural light")
        self.assertEqual(beat.continuity_notes, "same room as before")

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_narration_matching_the_script_word_for_word_is_accepted(self, mock_call):
        script = "Line one here. Line two here."
        mock_call.return_value = _fake_result(self._beats_json(["Line one here.", "Line two here."]))

        plan = generate_beat_plan(FAKE_CREDENTIALS, script)

        self.assertEqual(len(plan.beats), 2)
        mock_call.assert_called_once()  # no repair retry needed

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_narration_dropping_a_word_from_the_script_is_rejected(self, mock_call):
        script = "The sun set slowly over the quiet city."
        # Drops "quiet" -- must fail the verbatim-narration check every attempt.
        mock_call.return_value = _fake_result(self._beats_json(["The sun set slowly over the city."]))

        with self.assertRaises(ExternalServiceError):
            generate_beat_plan(FAKE_CREDENTIALS, script)

        self.assertEqual(mock_call.call_count, 2)  # initial + 1 bounded repair retry
        retry_system_prompt = mock_call.call_args_list[1].kwargs["system"]
        self.assertIn("quiet", retry_system_prompt)

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_narration_inventing_extra_words_is_rejected(self, mock_call):
        script = "He opened the door."
        mock_call.return_value = _fake_result(self._beats_json(["He slowly opened the heavy door."]))

        with self.assertRaises(ExternalServiceError):
            generate_beat_plan(FAKE_CREDENTIALS, script)

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_whitespace_only_differences_are_tolerated(self, mock_call):
        # Original script has a paragraph break; the model reflows it into
        # one beat separated by a single space -- same words, not a mismatch.
        script = "First paragraph.\n\nSecond paragraph."
        mock_call.return_value = _fake_result(self._beats_json(["First paragraph. Second paragraph."]))

        plan = generate_beat_plan(FAKE_CREDENTIALS, script)

        self.assertEqual(len(plan.beats), 1)

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_idea_and_character_description_reach_the_prompt(self, mock_call):
        mock_call.return_value = _fake_result(self._beats_json(["A story."]))

        generate_beat_plan(
            FAKE_CREDENTIALS, "A story.",
            idea="a man rebuilds his life", character_description="28yo man, grey hoodie",
            tone="warm", style="storytelling", target_duration=45.0,
        )

        user_message = mock_call.call_args.kwargs["user_message"]
        self.assertIn("a man rebuilds his life", user_message)
        self.assertIn("28yo man, grey hoodie", user_message)
        self.assertIn("warm", user_message)
        self.assertIn("45", user_message)

    @patch("app.api.v1.endpoints.beat_generate.call_structured")
    def test_no_context_leaves_user_message_as_the_bare_script(self, mock_call):
        mock_call.return_value = _fake_result(self._beats_json(["A story."]))

        generate_beat_plan(FAKE_CREDENTIALS, "A story.")

        self.assertEqual(mock_call.call_args.kwargs["user_message"], "A story.")


if __name__ == "__main__":
    unittest.main()
