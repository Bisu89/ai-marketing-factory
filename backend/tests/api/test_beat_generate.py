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

        plan = generate_beat_plan(FAKE_CREDENTIALS, "She thought he forgot their anniversary.")

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

        plan = generate_beat_plan(FAKE_CREDENTIALS, "A story script.")

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

        plan = generate_beat_plan(FAKE_CREDENTIALS, "A story script.")

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


if __name__ == "__main__":
    unittest.main()
