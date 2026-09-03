"""prepare_article_image: cover-crop to the render size, reject junk. httpx
is mocked -- no network.
"""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from PIL import Image

from app.modules.news.images import prepare_article_image


def _png_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _resp(content: bytes, status: int = 200) -> httpx.Response:
    return httpx.Response(status_code=status, content=content, request=httpx.Request("GET", "https://x/i"))


class PrepareArticleImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "img.jpg"

    def tearDown(self):
        self.tmp.cleanup()

    def test_landscape_photo_is_cover_cropped_to_exact_vertical_size(self):
        with patch("httpx.get", return_value=_resp(_png_bytes(1200, 630))):
            ok = prepare_article_image("https://x/i", self.dest, 1080, 1920)
        self.assertTrue(ok)
        with Image.open(self.dest) as out:
            self.assertEqual(out.size, (1080, 1920))

    def test_tiny_thumbnail_is_rejected(self):
        with patch("httpx.get", return_value=_resp(_png_bytes(100, 80))):
            self.assertFalse(prepare_article_image("https://x/i", self.dest, 1080, 1920))
        self.assertFalse(self.dest.exists())

    def test_non_image_body_is_rejected(self):
        with patch("httpx.get", return_value=_resp(b"<html>not an image</html>")):
            self.assertFalse(prepare_article_image("https://x/i", self.dest, 1080, 1920))

    def test_http_error_is_swallowed(self):
        with patch("httpx.get", side_effect=httpx.ConnectError("boom")):
            self.assertFalse(prepare_article_image("https://x/i", self.dest, 1080, 1920))
