"""Tests for Chinese Drama -> Vietnamese Shorts
(app/api/v1/endpoints/chinese_drama_dub.py + the video_composer service/
router additions it plugs into). The AI provider client is always mocked --
these tests never call a real OpenAI/Anthropic API, same convention as
tests/api/test_beat_generate.py's own docstring.
"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.v1.endpoints.chinese_drama_dub import (
    DUB_ASR_LANGUAGE,
    HOOK_MAX_WORDS,
    TITLE_MAX_CHARS,
    TITLE_MIN_CHARS,
    DubResult,
    _validate_dub_result,
    generate_dub,
)
from app.core.config import Settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import LLMCallResult
from app.modules.ai.transcribe_client import TRANSCRIBE_MODEL


def _fake_llm_result(translation: str, title: str, hook: str, refused: bool = False) -> LLMCallResult:
    text = json.dumps({"translation": translation, "title": title, "hook": hook})
    return LLMCallResult(
        text=text, refused=refused, provider="anthropic", model="claude-sonnet-5",
        input_tokens=100, output_tokens=50, latency_ms=10,
    )


_VALID_TITLE = "Cô ấy phát hiện bí mật động trời của chồng"  # 43 chars
assert TITLE_MIN_CHARS <= len(_VALID_TITLE) <= TITLE_MAX_CHARS


def _settings(**overrides) -> Settings:
    base = dict(
        library_dir="C:/tmp/chinese_drama_tests",
        anthropic_api_key="fake-anthropic-key",
        ai_provider="anthropic",
        openai_api_key="fake-openai-key",
    )
    base.update(overrides)
    return Settings(**base)


class ConfigConstantsTests(unittest.TestCase):
    def test_asr_model_and_language(self):
        self.assertEqual(TRANSCRIBE_MODEL, "gpt-4o-transcribe")
        self.assertEqual(DUB_ASR_LANGUAGE, "zh")

    def test_title_and_hook_bounds(self):
        self.assertEqual((TITLE_MIN_CHARS, TITLE_MAX_CHARS), (35, 55))
        self.assertEqual(HOOK_MAX_WORDS, 12)


class ValidateDubResultTests(unittest.TestCase):
    def test_valid_result_parses(self):
        result = _validate_dub_result({"translation": "Xin chào", "title": _VALID_TITLE, "hook": "Một câu hỏi ngắn"})
        self.assertEqual(result, DubResult(translation="Xin chào", title=_VALID_TITLE, hook="Một câu hỏi ngắn"))

    def test_empty_translation_rejected(self):
        with self.assertRaises(ValueError):
            _validate_dub_result({"translation": "  ", "title": _VALID_TITLE, "hook": "hook ngắn"})

    def test_title_too_short_rejected(self):
        with self.assertRaises(ValueError):
            _validate_dub_result({"translation": "x", "title": "Ngắn quá", "hook": "hook"})

    def test_title_too_long_rejected(self):
        long_title = "T" * (TITLE_MAX_CHARS + 1)
        with self.assertRaises(ValueError):
            _validate_dub_result({"translation": "x", "title": long_title, "hook": "hook"})

    def test_title_at_boundaries_accepted(self):
        for length in (TITLE_MIN_CHARS, TITLE_MAX_CHARS):
            title = "T" * length
            result = _validate_dub_result({"translation": "x", "title": title, "hook": "hook"})
            self.assertEqual(len(result.title), length)

    def test_hook_over_word_limit_rejected(self):
        hook = " ".join(["từ"] * (HOOK_MAX_WORDS + 1))
        with self.assertRaises(ValueError):
            _validate_dub_result({"translation": "x", "title": _VALID_TITLE, "hook": hook})

    def test_hook_at_word_limit_accepted(self):
        hook = " ".join(["từ"] * HOOK_MAX_WORDS)
        result = _validate_dub_result({"translation": "x", "title": _VALID_TITLE, "hook": hook})
        self.assertEqual(len(result.hook.split()), HOOK_MAX_WORDS)

    def test_empty_hook_rejected(self):
        with self.assertRaises(ValueError):
            _validate_dub_result({"translation": "x", "title": _VALID_TITLE, "hook": "   "})


class GenerateDubTests(unittest.TestCase):
    def setUp(self):
        self.settings = _settings()

    def test_missing_openai_key_rejected_before_any_call(self):
        settings = _settings(openai_api_key=None)
        with self.assertRaises(ValidationError):
            generate_dub(None, lambda: None, settings)

    @patch("app.api.v1.endpoints.chinese_drama_dub.transcribe_audio")
    @patch("app.api.v1.endpoints.chinese_drama_dub.extract_audio_track")
    @patch("app.api.v1.endpoints.chinese_drama_dub.call_structured")
    def test_asr_called_with_correct_model_and_language(self, mock_call_structured, mock_extract, mock_transcribe):
        from pathlib import Path

        mock_transcribe.return_value = SimpleNamespace(text="你好世界", segments=[])
        mock_call_structured.return_value = _fake_llm_result("Xin chào thế giới", _VALID_TITLE, "hook ngắn")

        on_transcribed_calls = []
        generate_dub(Path("fake_video.mp4"), lambda: on_transcribed_calls.append(1), self.settings)

        mock_extract.assert_called_once()
        mock_transcribe.assert_called_once()
        _, kwargs = mock_transcribe.call_args
        self.assertEqual(kwargs.get("language"), "zh")
        self.assertEqual(on_transcribed_calls, [1])  # on_transcribed fires exactly once, after ASR

    @patch("app.api.v1.endpoints.chinese_drama_dub.transcribe_audio")
    @patch("app.api.v1.endpoints.chinese_drama_dub.extract_audio_track")
    @patch("app.api.v1.endpoints.chinese_drama_dub.call_structured")
    def test_valid_llm_response_becomes_dub_result(self, mock_call_structured, mock_extract, mock_transcribe):
        from pathlib import Path

        mock_transcribe.return_value = SimpleNamespace(text="你好", segments=[])
        mock_call_structured.return_value = _fake_llm_result("Xin chào", _VALID_TITLE, "Một câu hook")

        result = generate_dub(Path("fake_video.mp4"), lambda: None, self.settings)

        self.assertEqual(result, DubResult(translation="Xin chào", title=_VALID_TITLE, hook="Một câu hook"))

    @patch("app.api.v1.endpoints.chinese_drama_dub.transcribe_audio")
    @patch("app.api.v1.endpoints.chinese_drama_dub.extract_audio_track")
    @patch("app.api.v1.endpoints.chinese_drama_dub.call_structured")
    def test_invalid_title_length_triggers_one_repair_retry_then_succeeds(self, mock_call_structured, mock_extract, mock_transcribe):
        from pathlib import Path

        mock_transcribe.return_value = SimpleNamespace(text="你好", segments=[])
        mock_call_structured.side_effect = [
            _fake_llm_result("Xin chào", "Quá ngắn", "hook"),  # title too short -- invalid
            _fake_llm_result("Xin chào", _VALID_TITLE, "hook"),  # repaired
        ]

        result = generate_dub(Path("fake_video.mp4"), lambda: None, self.settings)

        self.assertEqual(result.title, _VALID_TITLE)
        self.assertEqual(mock_call_structured.call_count, 2)
        retry_system_prompt = mock_call_structured.call_args_list[1].kwargs["system"]
        self.assertIn("previous response was invalid", retry_system_prompt)

    @patch("app.api.v1.endpoints.chinese_drama_dub.transcribe_audio")
    @patch("app.api.v1.endpoints.chinese_drama_dub.extract_audio_track")
    @patch("app.api.v1.endpoints.chinese_drama_dub.call_structured")
    def test_exhausted_retries_raise_external_service_error(self, mock_call_structured, mock_extract, mock_transcribe):
        from pathlib import Path

        mock_transcribe.return_value = SimpleNamespace(text="你好", segments=[])
        mock_call_structured.return_value = _fake_llm_result("Xin chào", "Quá ngắn", "hook")  # always invalid

        with self.assertRaises(ExternalServiceError):
            generate_dub(Path("fake_video.mp4"), lambda: None, self.settings)


if __name__ == "__main__":
    unittest.main()
