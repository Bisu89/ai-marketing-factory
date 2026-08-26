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

from app.modules.ai.image_client import (
    IMAGE_SIZE_DIMENSIONS,
    IMAGE_SIZE_LANDSCAPE,
    IMAGE_SIZE_PORTRAIT,
    IMAGE_SIZE_SQUARE,
    ImageGenError,
    generate_beat_image,
)


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


class SizeParameterTests(unittest.TestCase):
    """Real user request (docs/features/108-landscape-render-profile.md): a
    landscape render profile alongside this app's original portrait one --
    generate_beat_image must actually request the size it's given, not
    always the old hardcoded portrait default.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.output_path = Path(self.tmpdir.name) / "beat_b1.png"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_explicit_size_is_passed_through_to_the_openai_call(self):
        encoded = base64.b64encode(b"bytes").decode("ascii")
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.images.generate.return_value = _fake_response(encoded)
            generate_beat_image("fake-key", "a prompt", self.output_path, size=IMAGE_SIZE_LANDSCAPE)

        call_kwargs = mock_cls.return_value.images.generate.call_args.kwargs
        self.assertEqual(call_kwargs["size"], IMAGE_SIZE_LANDSCAPE)

    def test_omitted_size_defaults_to_portrait(self):
        encoded = base64.b64encode(b"bytes").decode("ascii")
        with patch("openai.OpenAI") as mock_cls:
            mock_cls.return_value.images.generate.return_value = _fake_response(encoded)
            generate_beat_image("fake-key", "a prompt", self.output_path)

        call_kwargs = mock_cls.return_value.images.generate.call_args.kwargs
        self.assertEqual(call_kwargs["size"], IMAGE_SIZE_PORTRAIT)

    def test_unsupported_size_is_rejected_before_any_api_call(self):
        with patch("openai.OpenAI") as mock_cls:
            with self.assertRaises(ImageGenError):
                generate_beat_image("fake-key", "a prompt", self.output_path, size="9999x9999")
            mock_cls.return_value.images.generate.assert_not_called()

    def test_size_dimensions_cover_all_three_supported_sizes(self):
        self.assertEqual(IMAGE_SIZE_DIMENSIONS[IMAGE_SIZE_PORTRAIT], (1024, 1536))
        self.assertEqual(IMAGE_SIZE_DIMENSIONS[IMAGE_SIZE_LANDSCAPE], (1536, 1024))
        self.assertEqual(IMAGE_SIZE_DIMENSIONS[IMAGE_SIZE_SQUARE], (1024, 1024))


if __name__ == "__main__":
    unittest.main()
