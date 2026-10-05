import unittest

from app.api.v1.endpoints.voice_test import (
    BOOKEND_AUTO,
    BOOKEND_SAME,
    build_runs,
    resolve_bookend_voice,
    split_sections,
)

KO_F = "ko-KR-SunHiNeural"
KO_M = "ko-KR-InJoonNeural"
VI_F = "vi-VN-HoaiMyNeural"
VI_M = "vi-VN-NamMinhNeural"

SCRIPT = """## ghi chú đầu file
## GIỚI THIỆU
Xin chào.

## TRUYỆN
## ghi chú cảnh 1
Đoạn một.
Đoạn hai.

## KẾT
Hẹn gặp lại.
"""


class SplitSectionsTests(unittest.TestCase):
    def test_intro_body_outro_in_order_and_notes_dropped(self):
        self.assertEqual(
            split_sections(SCRIPT),
            [("intro", "Xin chào."), ("body", "Đoạn một.\nĐoạn hai."), ("outro", "Hẹn gặp lại.")],
        )

    def test_plain_story_without_headers_is_one_body_section(self):
        self.assertEqual(split_sections("## note\nMột.\n\nHai."), [("body", "Một.\n\nHai.")])

    def test_empty_sections_are_skipped(self):
        self.assertEqual(split_sections("## GIỚI THIỆU\n\n## TRUYỆN\nNội dung."), [("body", "Nội dung.")])


class BookendVoiceTests(unittest.TestCase):
    def test_auto_flips_gender_within_the_same_language(self):
        self.assertEqual(resolve_bookend_voice(KO_F, BOOKEND_AUTO), KO_M)
        self.assertEqual(resolve_bookend_voice(VI_M, BOOKEND_AUTO), VI_F)

    def test_same_and_explicit(self):
        self.assertEqual(resolve_bookend_voice(KO_F, BOOKEND_SAME), KO_F)
        self.assertEqual(resolve_bookend_voice(KO_F, VI_M), VI_M)

    def test_runs_use_the_bookend_voice_only_for_intro_and_outro(self):
        runs = build_runs(split_sections(SCRIPT), KO_F, KO_M)
        self.assertEqual([v for _, v in runs], [KO_M, KO_F, KO_M])

    def test_same_voice_merges_into_one_run(self):
        runs = build_runs(split_sections(SCRIPT), KO_F, KO_F)
        self.assertEqual(len(runs), 1)


if __name__ == "__main__":
    unittest.main()
