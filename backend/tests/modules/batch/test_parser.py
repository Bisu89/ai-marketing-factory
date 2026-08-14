"""Tests for app.modules.batch.schemas.parse_scripts (Task 13 -- see
docs/features/40-batch-video-creation.md).
"""

import unittest

from app.modules.batch.schemas import parse_scripts


class ParseScriptsTests(unittest.TestCase):
    def test_single_script_no_separator(self):
        self.assertEqual(parse_scripts("She thought he forgot their anniversary."), ["She thought he forgot their anniversary."])

    def test_multiple_scripts_with_separator(self):
        raw = "Script one.\n---\nScript two.\n---\nScript three."
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two.", "Script three."])

    def test_leading_and_trailing_separators_are_dropped(self):
        raw = "---\nScript one.\n---\nScript two.\n---"
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two."])

    def test_empty_section_between_separators_is_dropped(self):
        raw = "Script one.\n---\n\n---\nScript two."
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two."])

    def test_whitespace_only_section_is_dropped(self):
        raw = "Script one.\n---\n   \n\t\n---\nScript two."
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two."])

    def test_windows_line_endings(self):
        raw = "Script one.\r\n---\r\nScript two.\r\n---\r\nScript three."
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two.", "Script three."])

    def test_unix_line_endings(self):
        raw = "Script one.\n---\nScript two."
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two."])

    def test_mac_classic_cr_only_line_endings(self):
        raw = "Script one.\r---\rScript two."
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two."])

    def test_leading_trailing_whitespace_trimmed_per_script(self):
        raw = "  Script one.  \n---\n\tScript two.\t"
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two."])

    def test_punctuation_is_preserved_exactly(self):
        raw = "She said, \"Where were you?\" -- and he had no answer... 100% true."
        self.assertEqual(parse_scripts(raw), [raw])

    def test_separator_must_be_on_its_own_line(self):
        # "---" embedded inside a sentence (e.g. an em-dash-like usage) must
        # not be treated as a script boundary.
        raw = "This is one script --- with a dash-like run, not a separator."
        self.assertEqual(parse_scripts(raw), [raw])

    def test_entirely_empty_input_yields_no_scripts(self):
        self.assertEqual(parse_scripts(""), [])

    def test_whitespace_only_input_yields_no_scripts(self):
        self.assertEqual(parse_scripts("   \n\n   "), [])

    def test_multi_line_scripts_preserve_internal_newlines(self):
        raw = "Line one.\nLine two.\n---\nAnother script,\nalso multi-line."
        self.assertEqual(parse_scripts(raw), ["Line one.\nLine two.", "Another script,\nalso multi-line."])

    def test_separator_with_surrounding_spaces_is_recognized(self):
        raw = "Script one.\n   ---   \nScript two."
        self.assertEqual(parse_scripts(raw), ["Script one.", "Script two."])

    def test_duplicate_scripts_are_preserved_as_separate_entries(self):
        raw = "Same script.\n---\nSame script."
        self.assertEqual(parse_scripts(raw), ["Same script.", "Same script."])


if __name__ == "__main__":
    unittest.main()
