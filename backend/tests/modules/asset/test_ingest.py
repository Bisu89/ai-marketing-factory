"""Tests for app.modules.asset.ingest (Task 15 -- see
docs/features/41-local-asset-ingestion.md). Pure functions, no DB -- matches
app.modules.batch.schemas.parse_scripts's own directly-unit-testable shape.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.core.exceptions import FileOperationError
from app.modules.asset.ingest import (
    CATEGORY_KEYWORDS,
    EMOTION_KEYWORDS,
    classify_orientation,
    classify_portrait_suitability,
    compute_file_hash,
    extract_audio_metadata,
    extract_image_metadata,
    extract_video_metadata,
    folder_tags_from_path,
    generate_image_thumbnail,
    generate_video_thumbnail,
    infer_category,
    infer_emotion,
    tokenize_filename,
)

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_image(path: Path, size: tuple[int, int], color=(120, 40, 200), fmt: str | None = None) -> Path:
    Image.new("RGB", size, color=color).save(path, format=fmt)
    return path


class ClassifyOrientationTests(unittest.TestCase):
    def test_portrait(self):
        self.assertEqual(classify_orientation(1080, 1920), "PORTRAIT")

    def test_landscape(self):
        self.assertEqual(classify_orientation(1920, 1080), "LANDSCAPE")

    def test_square(self):
        self.assertEqual(classify_orientation(1000, 1000), "SQUARE")


class ImageMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_jpg_portrait(self):
        path = _make_image(self.tmp_path / "p.jpg", (1080, 1920))
        meta = extract_image_metadata(path)
        self.assertEqual((meta.width, meta.height), (1080, 1920))
        self.assertEqual(meta.orientation, "PORTRAIT")
        self.assertEqual(meta.format, "JPEG")

    def test_png_landscape(self):
        path = _make_image(self.tmp_path / "l.png", (1920, 1080))
        meta = extract_image_metadata(path)
        self.assertEqual((meta.width, meta.height), (1920, 1080))
        self.assertEqual(meta.orientation, "LANDSCAPE")
        self.assertEqual(meta.format, "PNG")

    def test_webp_square(self):
        path = _make_image(self.tmp_path / "s.webp", (800, 800))
        meta = extract_image_metadata(path)
        self.assertEqual((meta.width, meta.height), (800, 800))
        self.assertEqual(meta.orientation, "SQUARE")

    def test_invalid_file_raises_file_operation_error(self):
        path = self.tmp_path / "fake.jpg"
        path.write_bytes(b"this is not a real image, deliberately corrupt")
        with self.assertRaises(FileOperationError):
            extract_image_metadata(path)

    def test_exif_orientation_is_respected(self):
        # Physically stored 1920x1080 (landscape) but EXIF-tagged as
        # rotated -- the *visual* size is 1080x1920 (portrait), and that's
        # what must be reported (section 11).
        path = self.tmp_path / "exif_rotated.jpg"
        img = Image.new("RGB", (1920, 1080), color=(200, 40, 40))
        exif = img.getexif()
        exif[0x0112] = 6  # Orientation tag -- a 90-degree rotation
        img.save(path, exif=exif)

        meta = extract_image_metadata(path)
        self.assertEqual((meta.width, meta.height), (1080, 1920))
        self.assertEqual(meta.orientation, "PORTRAIT")


@unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
class VideoMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_clip(self, name: str, width=640, height=360, duration=2.0, fps=24) -> Path:
        path = self.tmp_path / name
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"color=c=blue:s={width}x{height}:d={duration}:r={fps}",
                "-pix_fmt", "yuv420p", "-c:v", "libx264",
                str(path),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        return path

    def test_extracts_dimensions_duration_fps_codec(self):
        path = self._make_clip("clip.mp4", width=640, height=360, duration=2.0, fps=24)
        meta = extract_video_metadata(path)
        self.assertEqual((meta.width, meta.height), (640, 360))
        self.assertAlmostEqual(meta.duration_sec, 2.0, delta=0.2)
        self.assertAlmostEqual(meta.fps, 24.0, delta=0.5)
        self.assertEqual(meta.codec, "h264")

    def test_invalid_video_raises_file_operation_error(self):
        path = self.tmp_path / "fake.mp4"
        path.write_bytes(b"not a real video file")
        with self.assertRaises(FileOperationError):
            extract_video_metadata(path)


class AudioMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_track(self, name: str, duration=3.0) -> Path:
        path = self.tmp_path / name
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
                "-c:a", "libmp3lame",
                str(path),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        return path

    def test_extracts_duration_and_codec(self):
        path = self._make_track("track.mp3", duration=3.0)
        meta = extract_audio_metadata(path)
        self.assertAlmostEqual(meta.duration_sec, 3.0, delta=0.2)
        self.assertEqual(meta.codec, "mp3")

    def test_invalid_audio_raises_file_operation_error(self):
        path = self.tmp_path / "fake.mp3"
        path.write_bytes(b"not a real audio file")
        with self.assertRaises(FileOperationError):
            extract_audio_metadata(path)


class ThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_image_thumbnail_is_created_and_bounded_in_size(self):
        source = _make_image(self.tmp_path / "big.jpg", (3000, 2000))
        dest = self.tmp_path / "thumbs" / "1.jpg"
        generate_image_thumbnail(source, dest)
        self.assertTrue(dest.exists())
        with Image.open(dest) as thumb:
            self.assertLessEqual(thumb.width, 480)
            self.assertLessEqual(thumb.height, 480)

    @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg/ffprobe not found on PATH")
    def test_video_thumbnail_is_created(self):
        source = self.tmp_path / "clip.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=green:s=320x240:d=1:r=12",
                "-pix_fmt", "yuv420p", "-c:v", "libx264",
                str(source),
            ],
            check=True, stdin=subprocess.DEVNULL,
        )
        dest = self.tmp_path / "thumbs" / "2.jpg"
        generate_video_thumbnail(source, dest)
        self.assertTrue(dest.exists())
        with Image.open(dest) as thumb:
            self.assertGreater(thumb.width, 0)


class TokenizeFilenameTests(unittest.TestCase):
    def test_basic_underscore_separated_filename(self):
        self.assertEqual(
            tokenize_filename("woman_opening_gift_emotional.jpg"),
            ["woman", "opening", "gift", "emotional"],
        )

    def test_dash_and_space_separators(self):
        self.assertEqual(tokenize_filename("family-photo shoot.png"), ["family", "shoot"])

    def test_stopwords_and_numbers_dropped_when_safe(self):
        self.assertEqual(tokenize_filename("IMG_final_copy_01.jpg"), [])

    def test_meaningful_words_are_never_destroyed(self):
        # "image1080" and "copywriter" are not exact stopword matches --
        # substring containment must not strip them.
        tokens = tokenize_filename("image1080_copywriter.jpg")
        self.assertIn("image1080", tokens)
        self.assertIn("copywriter", tokens)

    def test_case_normalized_to_lowercase(self):
        self.assertEqual(tokenize_filename("Woman_Gift.jpg"), ["woman", "gift"])

    def test_duplicate_tokens_deduped(self):
        self.assertEqual(tokenize_filename("gift_gift_box.jpg"), ["gift", "box"])


class FolderTagsTests(unittest.TestCase):
    def test_couples_reunion_example_from_brief(self):
        root = Path("/assets")
        file_path = Path("/assets/couples/reunion/couple_hug.jpg")
        self.assertEqual(folder_tags_from_path(file_path, root), ["couples", "reunion"])

    def test_nested_underscored_folder_names_are_tokenized(self):
        root = Path("/assets")
        file_path = Path("/assets/family_photos/mother_daughter/img1.jpg")
        self.assertEqual(folder_tags_from_path(file_path, root), ["family", "photos", "mother", "daughter"])

    def test_file_directly_in_root_produces_no_folder_tags(self):
        root = Path("/assets")
        file_path = Path("/assets/image1.jpg")
        self.assertEqual(folder_tags_from_path(file_path, root), [])

    def test_file_outside_root_produces_no_folder_tags(self):
        root = Path("/assets")
        file_path = Path("/elsewhere/image1.jpg")
        self.assertEqual(folder_tags_from_path(file_path, root), [])


class CategoryInferenceTests(unittest.TestCase):
    def test_strong_couple_match(self):
        self.assertEqual(infer_category(["couple", "beach", "sunset"]), "Couple")

    def test_strong_family_match(self):
        self.assertEqual(infer_category(["mother", "children", "park"]), "Family")

    def test_no_match_returns_none(self):
        self.assertIsNone(infer_category(["mountain", "sunrise", "hiking"]))

    def test_every_real_catalog_value_has_a_keyword_entry(self):
        # Sanity check that the lexicon really is drawn from the real
        # catalog (app/db/seed.py's CATEGORIES), not an invented list.
        self.assertEqual(
            set(CATEGORY_KEYWORDS.keys()),
            {"Couple", "Family", "Military", "Proposal", "Transformation", "Comedy"},
        )


class EmotionInferenceTests(unittest.TestCase):
    def test_strong_happy_match_maps_to_vietnamese_catalog_value(self):
        self.assertEqual(infer_emotion(["happy", "smiling", "kids"]), "Vui")

    def test_strong_sad_match(self):
        self.assertEqual(infer_emotion(["sad", "crying", "alone"]), "Buồn")

    def test_no_match_returns_none(self):
        self.assertIsNone(infer_emotion(["kitchen", "table", "chair"]))

    def test_ambiguous_tie_returns_none_rather_than_guessing(self):
        # "funny" appears in both Cảm động's synonym-adjacent set is not
        # used, but Hài hước and this crafted tie: two categories each
        # scoring exactly 1 must not be force-resolved.
        tokens = ["happy", "sad"]  # one hit each for Vui and Buồn
        self.assertIsNone(infer_emotion(tokens))

    def test_every_real_catalog_value_has_a_keyword_entry(self):
        # Sanity check the lexicon keys are drawn from the real emotion
        # catalog (app/db/seed.py's EMOTIONS), not invented -- "Trung tính"
        # (Neutral) is deliberately absent since it's the "no signal"
        # default (represented as emotion=None), never a positive match.
        self.assertEqual(set(EMOTION_KEYWORDS.keys()), {"Vui", "Cảm động", "Hài hước", "Buồn", "Kịch tính"})


class PortraitSuitabilityTests(unittest.TestCase):
    def test_excellent_for_exact_9_16_portrait(self):
        self.assertEqual(classify_portrait_suitability(1080, 1920), "EXCELLENT")

    def test_good_for_close_but_not_exact_portrait(self):
        self.assertEqual(classify_portrait_suitability(1200, 1920), "GOOD")

    def test_crop_required_for_high_resolution_landscape(self):
        # Enough raw resolution (4000x3000) to crop down to a full
        # 1080x1920 portrait without upscaling -- just the wrong shape.
        self.assertEqual(classify_portrait_suitability(4000, 3000), "CROP_REQUIRED")

    def test_crop_required_for_high_resolution_square(self):
        self.assertEqual(classify_portrait_suitability(2400, 2400), "CROP_REQUIRED")

    def test_low_resolution_below_target(self):
        self.assertEqual(classify_portrait_suitability(640, 480), "LOW_RESOLUTION")

    def test_low_resolution_for_a_standard_1920x1080_landscape_photo(self):
        # A very common resolution, but its 1080px height can't cover a
        # 1920px-tall portrait frame without upscaling -- genuinely
        # low-resolution *for this specific target*, not a naive mislabel.
        self.assertEqual(classify_portrait_suitability(1920, 1080), "LOW_RESOLUTION")

    def test_none_when_dimensions_unknown(self):
        self.assertIsNone(classify_portrait_suitability(None, None))


class FileHashTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_same_content_different_filename_same_hash(self):
        content = b"identical bytes across two different files"
        path_a = self.tmp_path / "a.jpg"
        path_b = self.tmp_path / "subdir" / "b.jpg"
        path_b.parent.mkdir()
        path_a.write_bytes(content)
        path_b.write_bytes(content)
        self.assertEqual(compute_file_hash(path_a), compute_file_hash(path_b))

    def test_different_content_different_hash(self):
        path_a = self.tmp_path / "a.jpg"
        path_b = self.tmp_path / "b.jpg"
        path_a.write_bytes(b"content one")
        path_b.write_bytes(b"content two")
        self.assertNotEqual(compute_file_hash(path_a), compute_file_hash(path_b))

    def test_hash_is_deterministic_sha256_hex_digest(self):
        path = self.tmp_path / "a.jpg"
        path.write_bytes(b"hello world")
        import hashlib

        expected = hashlib.sha256(b"hello world").hexdigest()
        self.assertEqual(compute_file_hash(path), expected)


if __name__ == "__main__":
    unittest.main()
