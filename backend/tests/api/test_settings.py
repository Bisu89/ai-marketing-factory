"""Tests for app/api/v1/endpoints/settings.py's folder-browsing endpoint.
Real bug found in manual testing: os.listdrives() (Python 3.12+) doesn't
exist on this app's own pinned Python 3.11, so GET /settings/browse-folders
raised AttributeError with no path (drive-listing) argument -- silently
broken for both the Settings page's own "library dir" picker and the
Asset Library's "Import Folder" browse button.
"""

import sys
import tempfile
import unittest
from pathlib import Path

from app.api.v1.endpoints.settings import _list_windows_drives, browse_folders


class ListWindowsDrivesTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("win"), "Windows-only")
    def test_returns_at_least_one_real_existing_drive(self):
        drives = _list_windows_drives()
        self.assertGreater(len(drives), 0)
        for drive in drives:
            self.assertTrue(Path(drive).exists())

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows-only")
    def test_c_drive_is_present(self):
        # Every real Windows machine this app runs on has a C:\ -- a
        # concrete, deterministic assertion beyond "the list isn't empty".
        self.assertIn("C:\\", _list_windows_drives())


class BrowseFoldersEndpointTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("win"), "Windows-only")
    def test_no_path_lists_real_drives_without_raising(self):
        result = browse_folders(path=None)
        self.assertIsNone(result.current_path)
        self.assertIsNone(result.parent_path)
        self.assertGreater(len(result.folders), 0)

    def test_given_a_real_path_lists_its_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "child_a").mkdir()
            (Path(tmp) / "child_b").mkdir()
            (Path(tmp) / "not_a_folder.txt").write_text("x", encoding="utf-8")

            result = browse_folders(path=tmp)
            self.assertEqual(result.current_path, tmp)
            names = sorted(f.name for f in result.folders)
            self.assertEqual(names, ["child_a", "child_b"])


if __name__ == "__main__":
    unittest.main()
