"""Pure RSS/Atom fetch + parse adapter. No DB, no other module, no FastAPI
-- exercised directly by unit tests against static feed fixtures.

httpx does the network call (so connect/read timeouts and HTTP errors are
handled the same way as every other outbound request in this app);
feedparser only ever sees already-downloaded bytes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx

# A conservative per-feed cap -- a news feed that lists 200 back-articles
# should not create 200 rows on the first fetch. Newer entries first is the
# near-universal feed convention, so this keeps the most recent N.
MAX_ENTRIES_PER_FETCH = 40

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class FeedFetchError(Exception):
    """Any failure downloading or parsing a feed URL -- surfaced onto
    NewsSource.last_error, never raised past the service layer.
    """


@dataclass(frozen=True)
class FetchedEntry:
    guid: str
    title: str
    summary: str | None
    link: str | None
    image_url: str | None
    published_at: datetime | None

    @property
    def fingerprint(self) -> str:
        return normalized_title_fingerprint(self.title)


def normalized_title_fingerprint(title: str) -> str:
    """sha256 of a whitespace/case/punctuation-normalized title -- the
    cross-source dedupe key (the same syndicated story on two feeds hashes
    identically). Deliberately exact-normalized only, never fuzzy/semantic.
    """
    collapsed = _WS_RE.sub(" ", (title or "").strip().lower())
    stripped = collapsed.strip(" .,!?;:-\"'()[]")
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = _WS_RE.sub(" ", _TAG_RE.sub(" ", text)).strip()
    return cleaned or None


def _entry_published_at(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            try:
                return datetime.fromtimestamp(mktime(value), tz=timezone.utc)
            except (OverflowError, ValueError):
                return None
    return None


def _entry_image_url(entry) -> str | None:
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    for item in media:
        url = item.get("url")
        if url:
            return url
    for link in entry.get("links", []):
        if str(link.get("type", "")).startswith("image/") and link.get("href"):
            return link["href"]
    for enc in entry.get("enclosures", []):
        if str(enc.get("type", "")).startswith("image/") and enc.get("href"):
            return enc["href"]
    return None


def _entry_guid(entry) -> str | None:
    return entry.get("id") or entry.get("guid") or entry.get("link") or None


def parse_feed_bytes(raw: bytes) -> list[FetchedEntry]:
    parsed = feedparser.parse(raw)
    entries: list[FetchedEntry] = []
    for entry in parsed.entries[:MAX_ENTRIES_PER_FETCH]:
        guid = _entry_guid(entry)
        title = _strip_html(entry.get("title"))
        if not guid or not title:
            continue
        entries.append(
            FetchedEntry(
                guid=str(guid),
                title=title,
                summary=_strip_html(entry.get("summary") or entry.get("description")),
                link=entry.get("link") or None,
                image_url=_entry_image_url(entry),
                published_at=_entry_published_at(entry),
            )
        )
    return entries


def fetch_feed(feed_url: str, *, timeout: float = 15.0) -> list[FetchedEntry]:
    """Download and parse a feed URL. Raises FeedFetchError on any network
    or parse failure -- the caller records it on NewsSource.last_error.
    """
    try:
        response = httpx.get(
            feed_url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "AIContentLibrary/1.0 (+news feed reader)"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise FeedFetchError(f"Could not fetch feed: {exc}") from exc

    entries = parse_feed_bytes(response.content)
    if not entries:
        raise FeedFetchError("Feed contained no readable entries (not an RSS/Atom feed, or empty).")
    return entries
