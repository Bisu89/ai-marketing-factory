"""Tests for app.modules.ai.image_client (Task 59 -- see
docs/features/59-ai-image-generation.md). openai.OpenAI itself is mocked at
the module boundary (no real network call) -- these exercise this module's
own real decode/atomic-write/error-translation logic, mirroring
tests.modules.ai.test_llm_client's own "pure, mocked-boundary" style.
"""

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import openai

from app.modules.ai.image_client import ImageGenError, generate_beat_image


def _fake_response(b64_json: str | None):
    image = MagicMock()
    image.b64_json = b64_json
    response = MagicMock()
    response.data = [image]
    return response


class GenerateBeatImageTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.output_path = Path(self.tmpdir.name) / "sub" / "beat_b1.png"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_writes_real_decoded_bytes_atomically_to_the_output_path(self):
        raw = b"not a real png but real bytes"
        encoded = base64.b64encode(raw).decode("ascii")
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.images.generate.return_value = _fake_response(encoded)
            generate_beat_image("fake-key", "a prompt", self.output_path)

        self.assertTrue(self.output_path.exists())
        self.assertEqual(self.output_path.read_bytes(), raw)
        # No leftover .tmp file -- the atomic replace cleaned it up.
        self.assertFalse(self.output_path.with_suffix(".png.tmp").exists())

    def test_no_image_data_raises_image_gen_error(self):
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.images.generate.return_value = _fake_response(None)
            with self.assertRaises(ImageGenError):
                generate_beat_image("fake-key", "a prompt", self.output_path)
        self.assertFalse(self.output_path.exists())

    def test_undecodable_base64_raises_image_gen_error(self):
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.images.generate.return_value = _fake_response("not-valid-base64!!!")
            with self.assertRaises(ImageGenError):
                generate_beat_image("fake-key", "a prompt", self.output_path)
        self.assertFalse(self.output_path.exists())

    def test_openai_api_error_is_translated_to_image_gen_error(self):
        request = MagicMock()
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.images.generate.side_effect = openai.APIError("boom", request, body=None)
            with self.assertRaises(ImageGenError):
                generate_beat_image("fake-key", "a prompt", self.output_path)


if __name__ == "__main__":
    unittest.main()
