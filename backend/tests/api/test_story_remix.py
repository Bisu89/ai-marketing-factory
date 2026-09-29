"""Tests for the Story Remix rewrite step (app/api/v1/endpoints/story_remix.py).
The AI provider is always mocked -- the point of these tests is the
compliance gate (`_check_transformation` / `_check_same_language_overlap`),
not the AI call itself.
"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.v1.endpoints.story_remix import RewriteIn, SourceIn, _overlap_ratio, generate_story_remix
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import LLMCallResult

SETTINGS = SimpleNamespace(ai_provider="openai", openai_api_key="fake", anthropic_api_key="")


def _result(payload: dict) -> LLMCallResult:
    return LLMCallResult(
        text=json.dumps(payload), refused=False, provider="openai", model="m",
        input_tokens=None, output_tokens=None, latency_ms=1,
    )


def _beat(beat_type: str, narration: str) -> dict:
    return {"type": beat_type, "narration": narration, "visual_hint": "hint", "visual_description": "a scene"}


def _story(narrations: list[str], **transformation_overrides) -> dict:
    transformation = {
        "renamed_characters": True, "changed_setting": True, "changed_ending": True, "blended_sources": True,
    }
    transformation.update(transformation_overrides)
    types = ["HOOK"] + ["BUILD"] * (len(narrations) - 2) + ["ENDING"]
    return {
        "title": "Chương Mới",
        "new_setting": "một tông môn tu tiên trên núi mây",
        "beats": [_beat(t, n) for t, n in zip(types, narrations)],
        "transformation": transformation,
    }


SIX_BEATS = ["một hai ba bốn năm sáu"] * 6


class StoryRemixTransformationGateTests(unittest.TestCase):
    def test_untransformed_response_is_sent_back_for_repair(self):
        responses = [
            _result(_story(SIX_BEATS, renamed_characters=False, changed_setting=False)),
            _result(_story(SIX_BEATS)),
        ]
        payload = RewriteIn(sources=[SourceIn(text="nguồn gốc", language="vi", label="s1")], target_language="vi")
        with patch("app.api.v1.endpoints.story_remix.call_structured", side_effect=responses) as call:
            out = generate_story_remix(SETTINGS, payload)
        self.assertEqual(call.call_count, 2)
        self.assertIn("renamed_characters", call.call_args.kwargs["system"])
        self.assertIn("changed_setting", call.call_args.kwargs["system"])
        self.assertTrue(out.transformation.renamed_characters)

    def test_single_source_does_not_require_blended_sources(self):
        good = _result(_story(SIX_BEATS, blended_sources=False))
        payload = RewriteIn(sources=[SourceIn(text="nguồn gốc", language="vi", label="s1")], target_language="vi")
        with patch("app.api.v1.endpoints.story_remix.call_structured", return_value=good) as call:
            out = generate_story_remix(SETTINGS, payload)
        self.assertEqual(call.call_count, 1)
        self.assertFalse(out.transformation.blended_sources)

    def test_two_sources_require_blended_sources(self):
        responses = [
            _result(_story(SIX_BEATS, blended_sources=False)),
            _result(_story(SIX_BEATS)),
        ]
        payload = RewriteIn(
            sources=[SourceIn(text="a", language="vi", label="s1"), SourceIn(text="b", language="vi", label="s2")],
            target_language="vi",
        )
        with patch("app.api.v1.endpoints.story_remix.call_structured", side_effect=responses) as call:
            generate_story_remix(SETTINGS, payload)
        self.assertEqual(call.call_count, 2)
        self.assertIn("blended_sources", call.call_args.kwargs["system"])

    def test_wrong_first_or_last_beat_type_is_rejected(self):
        bad = _story(SIX_BEATS)
        bad["beats"][0]["type"] = "BUILD"  # not HOOK
        good = _story(SIX_BEATS)
        payload = RewriteIn(sources=[SourceIn(text="x", language="vi", label="s1")], target_language="vi")
        with patch("app.api.v1.endpoints.story_remix.call_structured", side_effect=[_result(bad), _result(good)]) as call:
            generate_story_remix(SETTINGS, payload)
        self.assertEqual(call.call_count, 2)

    def test_gives_up_after_retries(self):
        always_untransformed = _result(_story(SIX_BEATS, renamed_characters=False))
        payload = RewriteIn(sources=[SourceIn(text="x", language="vi", label="s1")], target_language="vi")
        with patch("app.api.v1.endpoints.story_remix.call_structured", return_value=always_untransformed):
            with self.assertRaises(ExternalServiceError):
                generate_story_remix(SETTINGS, payload)

    def test_no_provider_configured(self):
        settings = SimpleNamespace(ai_provider="openai", openai_api_key="", anthropic_api_key="")
        payload = RewriteIn(sources=[SourceIn(text="x", language="vi", label="s1")], target_language="vi")
        with self.assertRaises(ValidationError):
            generate_story_remix(settings, payload)


class SameLanguageOverlapTests(unittest.TestCase):
    def test_close_paraphrase_of_a_same_language_source_is_rejected(self):
        source_text = "một chàng trai xuyên không vào thế giới tu tiên và bất ngờ nhận được một hệ thống bí ẩn từ trên trời rơi xuống"
        # Near-verbatim reuse of the source's own phrasing.
        too_close = _story([source_text] * 6)
        transformed = _story(SIX_BEATS)
        payload = RewriteIn(sources=[SourceIn(text=source_text, language="vi", label="s1")], target_language="vi")
        with patch(
            "app.api.v1.endpoints.story_remix.call_structured", side_effect=[_result(too_close), _result(transformed)]
        ) as call:
            generate_story_remix(SETTINGS, payload)
        self.assertEqual(call.call_count, 2)
        self.assertIn("too close to source", call.call_args.kwargs["system"])

    def test_cross_language_source_is_not_checked_for_overlap(self):
        # Same literal text, but tagged as a different language than the
        # target -- must NOT trigger the overlap gate (see module docstring:
        # translation alone already drives raw overlap near zero for a real
        # cross-language pair, so the check is deliberately skipped instead
        # of being trivially satisfiable).
        source_text = "một hai ba bốn năm sáu bảy tám chín mười"
        same_text_story = _story([source_text] * 6)
        payload = RewriteIn(sources=[SourceIn(text=source_text, language="ko", label="s1")], target_language="vi")
        with patch("app.api.v1.endpoints.story_remix.call_structured", return_value=_result(same_text_story)) as call:
            generate_story_remix(SETTINGS, payload)
        self.assertEqual(call.call_count, 1)


class OverlapRatioTests(unittest.TestCase):
    def test_identical_text_has_full_overlap(self):
        text = "a b c d e f g h"
        self.assertEqual(_overlap_ratio(text, text), 1.0)

    def test_disjoint_text_has_no_overlap(self):
        self.assertEqual(_overlap_ratio("a b c d e f", "x y z w v u"), 0.0)

    def test_short_text_below_ngram_size_has_no_overlap(self):
        self.assertEqual(_overlap_ratio("a b c", "a b c d e f g h"), 0.0)


if __name__ == "__main__":
    unittest.main()
