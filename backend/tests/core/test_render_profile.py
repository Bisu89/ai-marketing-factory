import unittest

from app.core.exceptions import ValidationError
from app.core.render_profile import (
    DEFAULT_RENDER_PROFILE_NAME,
    PREVIEW,
    RENDER_PROFILES,
    SOCIAL_LANDSCAPE,
    SOCIAL_VERTICAL,
    get_render_profile,
)


class RenderProfileTests(unittest.TestCase):
    def test_social_vertical_matches_this_apps_documented_output_spec(self):
        self.assertEqual(SOCIAL_VERTICAL.width, 1080)
        self.assertEqual(SOCIAL_VERTICAL.height, 1920)
        self.assertEqual(SOCIAL_VERTICAL.fps, 30.0)
        self.assertEqual(SOCIAL_VERTICAL.video_codec, "h264")
        self.assertEqual(SOCIAL_VERTICAL.audio_codec, "aac")
        self.assertEqual(SOCIAL_VERTICAL.pixel_format, "yuv420p")

    def test_preview_is_smaller_and_lower_fps_than_social_vertical(self):
        self.assertLess(PREVIEW.width, SOCIAL_VERTICAL.width)
        self.assertLess(PREVIEW.height, SOCIAL_VERTICAL.height)
        self.assertLess(PREVIEW.fps, SOCIAL_VERTICAL.fps)

    def test_default_profile_name_is_social_vertical(self):
        self.assertEqual(DEFAULT_RENDER_PROFILE_NAME, "SOCIAL_VERTICAL")

    def test_get_render_profile_known_names_round_trip(self):
        self.assertIs(get_render_profile("SOCIAL_VERTICAL"), SOCIAL_VERTICAL)
        self.assertIs(get_render_profile("PREVIEW"), PREVIEW)

    def test_get_render_profile_unknown_name_raises_validation_error(self):
        with self.assertRaises(ValidationError) as ctx:
            get_render_profile("CINEMA_4K")
        self.assertIn("CINEMA_4K", str(ctx.exception))

    def test_render_profiles_registry_has_no_orphaned_names(self):
        for name, profile in RENDER_PROFILES.items():
            self.assertEqual(name, profile.name)

    def test_social_landscape_is_the_rotation_of_social_vertical(self):
        # Real user request (docs/features/108-landscape-render-profile.md):
        # a long-form 16:9 YouTube series alongside this app's original
        # 9:16 profile -- same total pixel count, just rotated, so identical
        # fps/codec choices remain correct for it.
        self.assertEqual(SOCIAL_LANDSCAPE.width, SOCIAL_VERTICAL.height)
        self.assertEqual(SOCIAL_LANDSCAPE.height, SOCIAL_VERTICAL.width)
        self.assertEqual(SOCIAL_LANDSCAPE.fps, SOCIAL_VERTICAL.fps)
        self.assertIs(get_render_profile("SOCIAL_LANDSCAPE"), SOCIAL_LANDSCAPE)


if __name__ == "__main__":
    unittest.main()
