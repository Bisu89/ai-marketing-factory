"""Tests for app.modules.ai.video_client (AI Storytelling Studio plan,
Phase 0 skeleton). No real provider is wired -- the default must be
unavailable and must raise, so the future AI_VIDEO stage degrades safely.
"""

import unittest
from pathlib import Path

from app.modules.ai.video_client import (
    NullVideoProvider,
    VideoGenError,
    VideoProvider,
    get_video_provider,
)


class NullProviderTests(unittest.TestCase):
    def test_default_provider_is_the_null_provider_and_unavailable(self):
        p = get_video_provider()
        self.assertIsInstance(p, NullVideoProvider)
        self.assertFalse(p.is_available())

    def test_generate_raises_videogenerror_not_a_bare_exception(self):
        with self.assertRaises(VideoGenError):
            get_video_provider().generate(
                prompt="a battle", duration_sec=5.0, output_path=Path("nowhere.mp4")
            )

    def test_null_provider_satisfies_the_protocol(self):
        self.assertIsInstance(NullVideoProvider(), VideoProvider)


if __name__ == "__main__":
    unittest.main()
