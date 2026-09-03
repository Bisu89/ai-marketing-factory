"""Pure parser tests for app.modules.news.feeds -- no network, no DB."""

import unittest

from app.modules.news.feeds import (
    MAX_ENTRIES_PER_FETCH,
    normalized_title_fingerprint,
    parse_feed_bytes,
)

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example News</title>
    <item>
      <title>Bank raises interest rate to 5 percent</title>
      <link>https://example.com/a</link>
      <guid>https://example.com/a</guid>
      <description>&lt;p&gt;The central bank &lt;b&gt;raised&lt;/b&gt; its rate today.&lt;/p&gt;</description>
      <pubDate>Wed, 03 Sep 2026 08:00:00 +0000</pubDate>
      <enclosure url="https://example.com/a.jpg" type="image/jpeg" length="1000"/>
    </item>
    <item>
      <title>Second story with no guid</title>
      <link>https://example.com/b</link>
      <description>Body two.</description>
    </item>
    <item>
      <link>https://example.com/c</link>
      <description>No title, should be skipped.</description>
    </item>
  </channel>
</rss>
"""


class ParseFeedTests(unittest.TestCase):
    def test_parses_entries_and_strips_html(self):
        entries = parse_feed_bytes(RSS)
        self.assertEqual(len(entries), 2)  # the title-less item is skipped

        first = entries[0]
        self.assertEqual(first.title, "Bank raises interest rate to 5 percent")
        self.assertEqual(first.guid, "https://example.com/a")
        self.assertEqual(first.summary, "The central bank raised its rate today.")
        self.assertEqual(first.image_url, "https://example.com/a.jpg")
        self.assertIsNotNone(first.published_at)

    def test_guid_falls_back_to_link(self):
        entries = parse_feed_bytes(RSS)
        self.assertEqual(entries[1].guid, "https://example.com/b")

    def test_caps_entry_count(self):
        items = "".join(
            f"<item><title>Story {i}</title><guid>g{i}</guid></item>" for i in range(MAX_ENTRIES_PER_FETCH + 10)
        )
        feed = f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'.encode()
        self.assertEqual(len(parse_feed_bytes(feed)), MAX_ENTRIES_PER_FETCH)


class FingerprintTests(unittest.TestCase):
    def test_normalization_ignores_case_whitespace_punctuation(self):
        a = normalized_title_fingerprint("  Bank Raises Interest Rate! ")
        b = normalized_title_fingerprint("bank raises interest rate")
        self.assertEqual(a, b)

    def test_different_titles_differ(self):
        self.assertNotEqual(
            normalized_title_fingerprint("Story one"), normalized_title_fingerprint("Story two")
        )
