"""Tests for the manhua recap script writer (app/api/v1/endpoints/manhua_recap.py).
The AI provider is always mocked; panels are tiny real PNGs in a temp dir.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.api.v1.endpoints.manhua_recap import ManhuaScriptIn, generate_manhua_script
from app.core.exceptions import ExternalServiceError, ValidationError
from app.modules.ai.llm_client import LLMCallResult

SETTINGS = SimpleNamespace(ai_provider="openai", openai_api_key="fake", anthropic_api_key="")


def _result(payload: dict) -> LLMCallResult:
    return LLMCallResult(
        text=json.dumps(payload), refused=False, provider="openai", model="m",
        input_tokens=None, output_tokens=None, latency_ms=1,
    )


class ManhuaRecapScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.paths = []
        for i in range(4):
            path = Path(self.tmp.name) / f"p{i + 1:03d}.png"
            Image.new("RGB", (400, 900), (i * 40, 100, 200)).save(path)
            self.paths.append(str(path))

    def tearDown(self):
        self.tmp.cleanup()

    def _beats(self, panels):
        return {"title": "Kiếm tiên lười biếng", "beats": [{"panel": p, "narration": f"câu {p}"} for p in panels]}

    def test_valid_response_returns_beats_and_sends_every_panel_labelled(self):
        with patch("app.api.v1.endpoints.manhua_recap.call_structured", return_value=_result(self._beats([1, 2, 4]))) as call:
            out = generate_manhua_script(SETTINGS, ManhuaScriptIn(panel_paths=self.paths))
        self.assertEqual([b.panel for b in out.beats], [1, 2, 4])
        images = call.call_args.kwargs["images"]
        self.assertEqual([img.label for img in images], ["Panel 1", "Panel 2", "Panel 3", "Panel 4"])
        self.assertEqual(images[0].media_type, "image/jpeg")

    def test_out_of_order_panels_trigger_one_repair_retry(self):
        responses = [_result(self._beats([2, 1, 3])), _result(self._beats([1, 2, 3]))]
        with patch("app.api.v1.endpoints.manhua_recap.call_structured", side_effect=responses) as call:
            out = generate_manhua_script(SETTINGS, ManhuaScriptIn(panel_paths=self.paths))
        self.assertEqual(call.call_count, 2)
        self.assertIn("strictly increasing", call.call_args.kwargs["system"])
        self.assertEqual([b.panel for b in out.beats], [1, 2, 3])

    def test_gives_up_after_the_retry(self):
        bad = _result(self._beats([1, 9, 10]))
        with patch("app.api.v1.endpoints.manhua_recap.call_structured", return_value=bad):
            with self.assertRaises(ExternalServiceError):
                generate_manhua_script(SETTINGS, ManhuaScriptIn(panel_paths=self.paths))

    def test_over_long_narration_is_sent_back_for_a_shorter_rewrite(self):
        long_line = " ".join(["chữ"] * 200)
        too_long = {"title": "t", "beats": [{"panel": p, "narration": long_line} for p in (1, 2, 3)]}
        responses = [_result(too_long), _result(self._beats([1, 2, 3]))]
        with patch("app.api.v1.endpoints.manhua_recap.call_structured", side_effect=responses) as call:
            out = generate_manhua_script(SETTINGS, ManhuaScriptIn(panel_paths=self.paths, target_duration=20))
        self.assertEqual(call.call_count, 2)
        self.assertIn("over the maximum", call.call_args.kwargs["system"])
        self.assertEqual(len(out.beats), 3)

    def test_missing_panel_file_is_a_validation_error(self):
        paths = [*self.paths[:3], str(Path(self.tmp.name) / "nope.png")]
        with self.assertRaises(ValidationError):
            generate_manhua_script(SETTINGS, ManhuaScriptIn(panel_paths=paths))

    def test_no_provider_configured(self):
        settings = SimpleNamespace(ai_provider="openai", openai_api_key="", anthropic_api_key="")
        with self.assertRaises(ValidationError):
            generate_manhua_script(settings, ManhuaScriptIn(panel_paths=self.paths))


if __name__ == "__main__":
    unittest.main()
