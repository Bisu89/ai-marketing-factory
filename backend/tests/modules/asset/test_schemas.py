import unittest

from pydantic import ValidationError

from app.modules.asset.schemas import AssetRegisterIn


class AssetRegisterInValidationTests(unittest.TestCase):
    def test_valid_payload(self):
        payload = AssetRegisterIn(
            filename="woman_portrait.jpg",
            path="/tmp/woman_portrait.jpg",
            type="image",
            width=1080,
            height=1920,
            tags=["woman", "emotional", "portrait"],
        )
        self.assertEqual(payload.type, "image")
        self.assertEqual(payload.tags, ["woman", "emotional", "portrait"])
        self.assertEqual(payload.source, "upload")

    def test_invalid_type_rejected(self):
        with self.assertRaises(ValidationError):
            AssetRegisterIn(filename="clip.mp4", path="/tmp/clip.mp4", type="document")

    def test_blank_filename_rejected(self):
        with self.assertRaises(ValidationError):
            AssetRegisterIn(filename="   ", path="/tmp/clip.mp4", type="video")

    def test_blank_path_rejected(self):
        with self.assertRaises(ValidationError):
            AssetRegisterIn(filename="clip.mp4", path="  ", type="video")

    def test_zero_width_rejected(self):
        with self.assertRaises(ValidationError):
            AssetRegisterIn(filename="clip.mp4", path="/tmp/clip.mp4", type="video", width=0)

    def test_negative_height_rejected(self):
        with self.assertRaises(ValidationError):
            AssetRegisterIn(filename="clip.mp4", path="/tmp/clip.mp4", type="video", height=-10)

    def test_negative_duration_rejected(self):
        with self.assertRaises(ValidationError):
            AssetRegisterIn(filename="clip.mp4", path="/tmp/clip.mp4", type="video", duration_sec=-1.0)

    def test_zero_duration_rejected(self):
        with self.assertRaises(ValidationError):
            AssetRegisterIn(filename="clip.mp4", path="/tmp/clip.mp4", type="video", duration_sec=0.0)

    def test_all_three_asset_types_accepted(self):
        for asset_type in ("image", "video", "audio"):
            payload = AssetRegisterIn(filename=f"x.{asset_type}", path=f"/tmp/x.{asset_type}", type=asset_type)
            self.assertEqual(payload.type, asset_type)


if __name__ == "__main__":
    unittest.main()
