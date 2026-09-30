import tempfile
import unittest
from pathlib import Path

from app.core.output_naming import (
    MAX_LABEL_LEN,
    find_labeled_dir,
    labeled_name,
    labeled_video_filename,
    resolve_labeled_dir,
    safe_label,
)


class SafeLabelTests(unittest.TestCase):
    def test_strips_windows_unsafe_characters(self):
        self.assertEqual(safe_label('Ep1: Why? "Judas" / Short.'), "Ep1 Why Judas Short")

    def test_keeps_vietnamese_diacritics(self):
        self.assertEqual(safe_label("Đại Quản Gia  là Ma Hoàng"), "Đại Quản Gia là Ma Hoàng")

    def test_none_for_blank_or_reserved(self):
        self.assertIsNone(safe_label(None))
        self.assertIsNone(safe_label("  ?? "))
        self.assertIsNone(safe_label("con"))

    def test_truncated(self):
        self.assertEqual(len(safe_label("a" * 200)), MAX_LABEL_LEN)


class LabeledNameTests(unittest.TestCase):
    def test_prefix_id_label(self):
        self.assertEqual(labeled_name("job", 12, "Tập 1: Mở đầu"), "job_12_Tập 1 Mở đầu")
        self.assertEqual(labeled_video_filename("job", 12, "Tập 1"), "job_12_Tập 1.mp4")

    def test_falls_back_to_bare_id(self):
        self.assertEqual(labeled_name("job", 12, None), "job_12")
        self.assertEqual(labeled_name("", 7, "???"), "7")
        self.assertEqual(labeled_name("", 7, "Story"), "7_Story")


class ResolveLabeledDirTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_new_dir_is_labeled(self):
        self.assertEqual(resolve_labeled_dir(self.root, "job", 3, "Hello"), self.root / "job_3_Hello")
        self.assertIsNone(find_labeled_dir(self.root, "job", 3))

    def test_reuses_legacy_bare_dir(self):
        (self.root / "job_3").mkdir()
        self.assertEqual(resolve_labeled_dir(self.root, "job", 3, "Hello"), self.root / "job_3")

    def test_reuses_existing_dir_after_title_change(self):
        (self.root / "job_3_Old title").mkdir()
        self.assertEqual(resolve_labeled_dir(self.root, "job", 3, "New title"), self.root / "job_3_Old title")

    def test_does_not_match_a_longer_id(self):
        (self.root / "job_31_Other").mkdir()
        self.assertEqual(resolve_labeled_dir(self.root, "job", 3, "Mine"), self.root / "job_3_Mine")

    def test_empty_prefix(self):
        (self.root / "5").mkdir()
        self.assertEqual(find_labeled_dir(self.root, "", 5), self.root / "5")
        self.assertIsNone(find_labeled_dir(self.root, "", 55))


if __name__ == "__main__":
    unittest.main()
