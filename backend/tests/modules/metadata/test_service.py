"""Tests for Task 27 -- see docs/features/53-thumbnail-metadata-package.md.
Pure, in-memory tests of app.modules.metadata.service -- no I/O, no AI
call, deterministic string transforms only.
"""

import unittest

from app.modules.metadata.schemas import ContentInputs, MetadataError
from app.modules.metadata.service import (
    derive_category,
    derive_description,
    derive_hashtags,
    derive_title,
    normalize_hashtag,
    normalize_hashtags,
    validate_description,
    validate_hashtags,
    validate_title,
)


def _inputs(**overrides) -> ContentInputs:
    base = dict(
        core_message="She finally told him why she left after ten years",
        cta="Follow for more real stories",
        topic="long distance relationships",
        angle="betrayal and healing",
        emotion="bittersweet",
        tone="reflective",
        hook_text="Why did she really leave?",
        project_name="Project 1",
    )
    base.update(overrides)
    return ContentInputs(**base)


class TitleTests(unittest.TestCase):
    def test_manual_title_always_wins(self):
        title = derive_title(_inputs(), "My Manual Title", max_chars=70)
        self.assertEqual(title, "My Manual Title")

    def test_manual_title_wins_even_when_core_message_present(self):
        title = derive_title(_inputs(core_message="Something else entirely"), "Chosen Title", max_chars=70)
        self.assertEqual(title, "Chosen Title")

    def test_falls_back_to_core_message_when_no_manual_title(self):
        title = derive_title(_inputs(), None, max_chars=70)
        self.assertEqual(title, "She finally told him why she left after ten years")

    def test_falls_back_to_hook_text_when_no_core_message(self):
        # "?" is itself an illegal filesystem character (section 23) and is
        # stripped from every derived title, generated or manual alike.
        title = derive_title(_inputs(core_message=None), None, max_chars=70)
        self.assertEqual(title, "Why did she really leave")

    def test_falls_back_to_project_name_as_last_resort(self):
        title = derive_title(_inputs(core_message=None, hook_text=None), None, max_chars=70)
        self.assertEqual(title, "Project 1")

    def test_raises_title_invalid_when_nothing_available(self):
        with self.assertRaises(MetadataError) as ctx:
            derive_title(_inputs(core_message=None, hook_text=None, project_name=None), None, max_chars=70)
        self.assertEqual(ctx.exception.code, "TITLE_INVALID")

    def test_long_title_is_truncated_at_word_boundary(self):
        long_message = "This is a very long core message that goes on and on well past the character limit for sure"
        title = derive_title(_inputs(core_message=long_message), None, max_chars=40)
        self.assertLessEqual(len(title), 40)
        self.assertTrue(long_message.startswith(title))

    def test_validate_title_rejects_empty(self):
        with self.assertRaises(MetadataError) as ctx:
            validate_title("   ", 70)
        self.assertEqual(ctx.exception.code, "TITLE_INVALID")

    def test_validate_title_rejects_illegal_filesystem_characters(self):
        with self.assertRaises(MetadataError) as ctx:
            validate_title('Bad: Title / With * Illegal ? Chars', 70)
        self.assertEqual(ctx.exception.code, "TITLE_INVALID")

    def test_validate_title_rejects_too_long(self):
        with self.assertRaises(MetadataError):
            validate_title("x" * 100, 70)

    def test_manual_title_strips_illegal_filesystem_characters(self):
        title = derive_title(_inputs(), "Weird: Title / Here", max_chars=70)
        self.assertNotIn(":", title)
        self.assertNotIn("/", title)


class DescriptionTests(unittest.TestCase):
    def test_manual_description_used_verbatim(self):
        desc = derive_description(_inputs(), "My own description.", [], cta_enabled=True, max_chars=500)
        self.assertEqual(desc, "My own description.")

    def test_manual_description_never_gets_hashtags_appended(self):
        desc = derive_description(_inputs(), "My own description.", ["#Tag1", "#Tag2"], cta_enabled=True, max_chars=500)
        self.assertNotIn("#Tag1", desc)

    def test_generated_description_includes_summary_cta_and_hashtags(self):
        desc = derive_description(_inputs(), None, ["#LoveStory"], cta_enabled=True, max_chars=500)
        self.assertIn("She finally told him why she left after ten years", desc)
        self.assertIn("Follow for more real stories", desc)
        self.assertIn("#LoveStory", desc)

    def test_cta_disabled_omits_cta_line(self):
        desc = derive_description(_inputs(), None, [], cta_enabled=False, max_chars=500)
        self.assertNotIn("Follow for more real stories", desc)

    def test_raises_description_invalid_when_nothing_available(self):
        with self.assertRaises(MetadataError) as ctx:
            derive_description(_inputs(core_message=None, hook_text=None, project_name=None), None, [], cta_enabled=True, max_chars=500)
        self.assertEqual(ctx.exception.code, "DESCRIPTION_INVALID")

    def test_long_description_is_truncated_but_keeps_hashtags_intact(self):
        long_message = "word " * 200
        desc = derive_description(_inputs(core_message=long_message), None, ["#Keep"], cta_enabled=False, max_chars=100)
        self.assertLessEqual(len(desc), 100)
        self.assertTrue(desc.endswith("#Keep"))

    def test_validate_description_rejects_empty(self):
        with self.assertRaises(MetadataError) as ctx:
            validate_description("", 500)
        self.assertEqual(ctx.exception.code, "DESCRIPTION_INVALID")


class HashtagNormalizationTests(unittest.TestCase):
    def test_normalize_variants_of_the_same_phrase_produce_the_same_tag(self):
        self.assertEqual(normalize_hashtag("#LoveStory"), "#LoveStory")
        self.assertEqual(normalize_hashtag("love story"), "#LoveStory")
        self.assertEqual(normalize_hashtag("love-story"), "#LoveStory")

    def test_empty_or_punctuation_only_normalizes_to_none(self):
        self.assertIsNone(normalize_hashtag("   "))
        self.assertIsNone(normalize_hashtag("###"))
        self.assertIsNone(normalize_hashtag("-"))

    def test_normalize_hashtags_removes_duplicates_case_insensitively(self):
        result = normalize_hashtags(["#Love", "love", "#love", "love-story"], max_count=10)
        self.assertEqual(result, ["#Love", "#LoveStory"])

    def test_normalize_hashtags_drops_empty_entries(self):
        result = normalize_hashtags(["#Love", "", "   ", "#Story"], max_count=10)
        self.assertEqual(result, ["#Love", "#Story"])

    def test_normalize_hashtags_caps_at_max_count(self):
        result = normalize_hashtags(["#One", "#Two", "#Three", "#Four"], max_count=2)
        self.assertEqual(result, ["#One", "#Two"])

    def test_validate_hashtags_rejects_too_many(self):
        with self.assertRaises(MetadataError) as ctx:
            validate_hashtags(["#A", "#B", "#C"], max_count=2)
        self.assertEqual(ctx.exception.code, "HASHTAG_INVALID")

    def test_validate_hashtags_rejects_missing_hash_prefix(self):
        with self.assertRaises(MetadataError) as ctx:
            validate_hashtags(["NoHash"], max_count=5)
        self.assertEqual(ctx.exception.code, "HASHTAG_INVALID")


class DeriveHashtagsTests(unittest.TestCase):
    def test_manual_hashtags_always_win(self):
        result = derive_hashtags(_inputs(), ["#MyOwnTag"], max_count=8)
        self.assertEqual(result, ["#MyOwnTag"])

    def test_manual_hashtags_are_still_normalized(self):
        result = derive_hashtags(_inputs(), ["  My Tag  ", "my-tag"], max_count=8)
        self.assertEqual(result, ["#MyTag"])

    def test_generated_from_content_brief_fields(self):
        result = derive_hashtags(_inputs(), None, max_count=8)
        self.assertIn("#LongDistanceRelationships", result)
        self.assertIn("#BetrayalAndHealing", result)

    def test_generated_hashtags_respect_max_count(self):
        result = derive_hashtags(_inputs(), None, max_count=2)
        self.assertLessEqual(len(result), 2)

    def test_no_content_available_returns_empty_list_not_an_error(self):
        result = derive_hashtags(_inputs(topic=None, angle=None, emotion=None, tone=None), None, max_count=8)
        self.assertEqual(result, [])


class CategoryTests(unittest.TestCase):
    def test_uses_topic_as_category(self):
        self.assertEqual(derive_category(_inputs()), "long distance relationships")

    def test_falls_back_to_general_when_no_topic(self):
        self.assertEqual(derive_category(_inputs(topic=None)), "general")


if __name__ == "__main__":
    unittest.main()
