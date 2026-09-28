"""motion fit_mode="blur_fill": the whole source image is kept (contained, centred)
over a blurred cover-scaled copy, at the output aspect ratio."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.modules.motion.renderer import compose_blur_fill


class ComposeBlurFillTests(unittest.TestCase):
    def test_wide_panel_is_kept_whole_and_centred_at_output_aspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "wide.png"
            # a 2:1 panel: solid red, with a white 10px border so its edges are detectable
            img = Image.new("RGB", (800, 400), (255, 255, 255))
            img.paste(Image.new("RGB", (780, 380), (255, 0, 0)), (10, 10))
            img.save(src)
            out = compose_blur_fill(src, 1080, 1920, Path(tmp) / "out.png")
            with Image.open(out) as result:
                self.assertEqual(result.size, (2160, 3840))  # 2x output, 9:16
                # contained: full width, centred vertically -> the panel's left/right
                # white borders survive (a cover-crop would have cut them off)
                mid_y = 3840 // 2
                self.assertEqual(result.getpixel((5, mid_y)), (255, 255, 255))
                self.assertEqual(result.getpixel((2154, mid_y)), (255, 255, 255))
                self.assertEqual(result.getpixel((1080, mid_y)), (255, 0, 0))
                # above the panel is the blurred, darkened background, not black bars
                top = result.getpixel((1080, 100))
                self.assertGreater(top[0], 100)
                self.assertLess(top[0], 255)


if __name__ == "__main__":
    unittest.main()
