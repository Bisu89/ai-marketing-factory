"""Download one comic chapter's page images from a supported site.

Shared by `tools/manhua_recap/recap.py`'s `fetch` command (desktop-local,
no server needed) and `POST /manhua-recap/fetch` (the in-app "paste a
link" form, feature 154) -- one implementation, so a new site or a dedup
fix lands in both places at once.

-- Sites --
manhuavn2.com chapter pages list their page images as <img class="lazy"
data-original="...">; the same markup is used for the sidebar's cover
thumbnails, which all live under /Pictures/Truyen/. VIP chapters are marked
"isAccessibleForFree": false and carry no page images.
cotruyenday.com (.../truyen-tranh/<slug>/chapter-N, no .html) serves page
images from images.jino277.work/prod/chapters/...; the URLs can contain
spaces, so they are percent-encoded before download. Chapters past the
free ones (ch.11+ on Dai Quan Gia, 2026-09-28) come back with no images.
zettruyen*.com (.../truyen-tranh/<slug>/chuong-N) serves pages from
cdnN.zetimage.com/<slug>/<N>/<i>.jpg; that CDN answers 403 without a
Referer from the site (hotlink protection), and /thumb/ holds sidebar covers.
truyenqq.com.vn (.../<slug>/chapter-N, no "truyen-tranh/" segment) serves
page images as <img data-src="https://sN.cc3t.net/chapters/...">; that CDN
also 403s without a Referer, same as zettruyen.

-- Recurring filler images --
Every site inserts its own ad/domain-name/"read at ..."/anti-reup splash
images into every chapter. Most are byte-identical every time (caught by
exact sha1), but some get re-encoded slightly differently by the CDN on
each request -- same picture, different bytes. So pages are also compared
by a coarse perceptual hash (256-bit average hash: resize to 16x16
grayscale, one bit per pixel vs the mean) and treated as the same recurring
image if within PHASH_MAX_DIST bits of a previously-seen one. Kept strict
(~2% of bits) -- real story panels essentially never land that close to
each other by chance, but a recompressed duplicate does.

Both caches are process-wide (not keyed by site/series) so they keep
getting better at recognizing a site's recurring filler over time, and
live on disk (not in the DB) so the CLI tool works without the backend
running. Each cached hash remembers the chapter URLs it was seen in, and
only counts as filler when seen in a *different* chapter -- so re-fetching
a chapter doesn't flag its own pages. A page repeated inside one chapter is
the site serving it twice, not an ad: the first copy is kept (see
_find_filler).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from app.core.config import IS_FROZEN

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
COVER_PATH = "/Pictures/Truyen/"

PHASH_SIZE = 16          # 16x16 = 256-bit average hash
PHASH_MAX_DIST = 6       # bits that may differ and still count as "the same image"


def _cache_dir() -> Path:
    # Same dev-vs-frozen split as app.core.config's own defaults (backend/data
    # in dev, %LOCALAPPDATA%/AIContentLibrary/data in a packaged build) --
    # resolved from this file's own location, not the caller's cwd, so the
    # CLI tool (run from the repo root) and the API server (run from
    # backend/) share the exact same cache file.
    if not IS_FROZEN:
        return Path(__file__).resolve().parents[3] / "data"
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "AIContentLibrary" / "data"


COMMON_HASH_CACHE = _cache_dir() / "manhua_common_hashes.json"


class FetchError(Exception):
    """Bad URL, VIP/locked chapter, or no page images found."""


@dataclass
class FetchChapterResult:
    n: int | None
    saved: int
    skipped: int


@dataclass
class FetchResult:
    total_saved: int
    total_skipped: int
    chapters: list[FetchChapterResult]


def _load_common_hashes() -> dict:
    try:
        data = json.loads(COMMON_HASH_CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"exact": {}, "phash": {}}
    if "exact" not in data:  # pre-perceptual-hash cache: a flat {sha1: count} dict
        data = {"exact": data, "phash": {}}
    return data


def _ahash(data: bytes) -> str | None:
    """Average hash: coarse fingerprint that survives re-encoding/minor
    resizing. None if the bytes aren't a decodable image (never blocks a
    download on this -- exact-hash matching still applies)."""
    try:
        im = Image.open(io.BytesIO(data)).convert("L").resize((PHASH_SIZE, PHASH_SIZE), Image.LANCZOS)
    except Exception:
        return None
    pixels = list(im.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p >= avg else "0" for p in pixels)
    return f"{int(bits, 2):0{len(bits) // 4}x}"


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _closest_phash(ph: str, candidates: dict) -> str | None:
    """The key in candidates closest to ph within PHASH_MAX_DIST, or None."""
    best, best_dist = None, PHASH_MAX_DIST + 1
    for other in candidates:
        d = _hamming(ph, other)
        if d <= PHASH_MAX_DIST and d < best_dist:
            best, best_dist = other, d
    return best


MAX_CACHE_CHAPTERS = 5   # chapters remembered per cached hash


def _bucket_pages(exact_hashes: list[str], phashes: list[str | None]) -> list[int]:
    """Bucket id per page: pages with the same sha1, or a perceptual hash
    within PHASH_MAX_DIST of a bucket's first member, share a bucket."""
    reps: list[str | None] = []   # one representative perceptual hash per bucket
    by_exact: dict[str, int] = {}
    out: list[int] = []
    for h, ph in zip(exact_hashes, phashes):
        bucket = by_exact.get(h)
        if bucket is None and ph is not None:
            bucket = next((b for b, rep in enumerate(reps) if rep is not None and _hamming(ph, rep) <= PHASH_MAX_DIST), None)
        if bucket is None:
            bucket = len(reps)
            reps.append(ph)
        by_exact[h] = bucket
        out.append(bucket)
    return out


def _entry_chapters(entry) -> list[str]:
    """Chapters a cached hash was seen in. Old caches stored a bare count
    that can't tell a re-fetched chapter from a recurring ad, so only counts
    of 3+ (clearly recurring) survive, as opaque placeholders that never
    equal a real chapter URL; smaller counts are forgotten."""
    if isinstance(entry, list):
        return entry
    if isinstance(entry, int) and entry >= 3:
        return [f"legacy{i}" for i in range(min(entry, MAX_CACHE_CHAPTERS))]
    return []


def _remember(table: dict, key: str, chapter: str) -> None:
    chapters = list(_entry_chapters(table.get(key)))
    if chapter not in chapters:
        chapters.append(chapter)
    table[key] = chapters[-MAX_CACHE_CHAPTERS:]


def _find_filler(
    chapter_of: list[int], chapter_keys: list[str], exact_hashes: list[str], phashes: list[str | None], cache: dict,
) -> list[bool]:
    """Which pages are recurring ad/filler images (and updates `cache`).

    - Same image on pages of *different* chapters in this run: filler, every copy.
    - Same image repeated within *one* chapter: the site just served the page
      twice -- keep the first copy, drop the rest.
    - Same image already cached from a *different* chapter: filler. Re-fetching
      a chapter never flags its own pages (the cache keys on chapter URL)."""
    buckets = _bucket_pages(exact_hashes, phashes)
    members: dict[int, list[int]] = {}
    for i, b in enumerate(buckets):
        members.setdefault(b, []).append(i)
    filler = [False] * len(buckets)
    for idx in members.values():
        if len(idx) < 2:
            continue
        if len({chapter_of[i] for i in idx}) > 1:
            for i in idx:
                filler[i] = True
        else:
            for i in idx[1:]:
                filler[i] = True

    for i, (h, ph) in enumerate(zip(exact_hashes, phashes)):
        key = chapter_keys[chapter_of[i]]
        near = _closest_phash(ph, cache["phash"]) if ph is not None else None
        seen_elsewhere = any(c != key for c in _entry_chapters(cache["exact"].get(h)))
        if near is not None:
            seen_elsewhere = seen_elsewhere or any(c != key for c in _entry_chapters(cache["phash"][near]))
        if seen_elsewhere:
            filler[i] = True
        _remember(cache["exact"], h, key)
        if ph is not None:
            _remember(cache["phash"], near or ph, key)  # fold near-dups into one key, don't grow unbounded
    return filler


def _get(url: str, timeout: int = 60, referer: str | None = None) -> bytes:
    url = urllib.parse.quote(url, safe=":/%?=&")
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.URLError as exc:
        raise FetchError(f"Could not fetch {url}: {exc}") from exc


# zettruyen*.com sits behind Cloudflare and resets the raw TLS connection for
# any non-browser client -- plain urllib/curl and even a TLS-fingerprint-
# spoofed client (curl_cffi impersonating Chrome) get the same reset, so the
# chapter HTML has to come from a real (headless) browser instead. Needs
# `python -m playwright install chromium` once.
BROWSER_ONLY_SITES = ("zettruyen",)


def _get_html_via_browser(url: str, page) -> str:
    try:
        page.goto(url, timeout=45_000, wait_until="domcontentloaded")
    except Exception as exc:
        raise FetchError(f"Could not fetch {url} (headless browser): {exc}") from exc
    return page.content()


def _chapter_page_urls(url: str, page=None) -> list[str]:
    if page is not None and any(site in url for site in BROWSER_ONLY_SITES):
        html = _get_html_via_browser(url, page)
    else:
        html = _get(url).decode("utf-8", errors="replace")
    if re.search(r'"isAccessibleForFree"\s*:\s*false', html):
        raise FetchError(f"{url} is VIP/locked on the site -- pick free chapters.")
    if "cotruyenday.com" in url:
        urls = list(dict.fromkeys(re.findall(r'["\'](https?://images\.jino277\.work/prod/chapters/[^"\']+)', html)))
    elif "zettruyen" in url:
        urls = [u for u in dict.fromkeys(re.findall(r'(https?://cdn\d*\.zetimage\.com/[^"\'\s\\]+)', html))
                if "/thumb/" not in u]
    elif "truyenqq" in url:
        urls = list(dict.fromkeys(re.findall(r'(https?://[\w.-]+\.cc3t\.net/chapters/[^"\'\s\\]+)', html)))
    else:
        urls = [u for u in re.findall(r'data-original="([^"]+)"', html) if COVER_PATH not in u]
    if not urls:
        raise FetchError(f"No page images found on {url} -- a chapter URL? (cotruyenday: only free / logged-out chapters work)")
    return urls


def fetch_chapters(
    url: str, chapter_dir: Path, count: int = 1, on_progress: Callable[[int | None, int, int], None] | None = None,
) -> FetchResult:
    """count > 1: also fetch the next chapters by bumping `-chapter-N` /
    `-chuong-N` in the URL. Pages are named c<chapter>_<page>.jpg (or
    <page>.jpg for a single chapter) so `cut` stacks them in reading order.
    Downloads every chapter's images first, then writes -- so a filler
    image that repeats can be recognized (see COMMON_HASH_CACHE) and
    dropped before any file is written, keeping page numbering gap-free.

    `on_progress(chapter_n, done, total)` is called after each page
    downloads -- the CLI uses it to print a progress line; the API request
    (one chapter or a handful, seconds long) just leaves it out."""
    match = re.search(r"(?:chapter|chuong)-(\d+)(\.html)?/?$", url)
    if count > 1 and not match:
        raise FetchError("count > 1 needs a URL ending in chapter-N / chuong-N (or -chapter-N.html)")
    referer = "{0.scheme}://{0.netloc}/".format(urllib.parse.urlparse(url))
    chapter_dir.mkdir(parents=True, exist_ok=True)

    chapter_keys: list[str] = []

    def _run(page) -> list[tuple[int | None, list[bytes]]]:
        fetched: list[tuple[int | None, list[bytes]]] = []
        for k in range(count):
            n = int(match.group(1)) + k if match else None
            chapter_url = url if k == 0 else url[:match.start(1)] + str(n) + url[match.end(1):]
            chapter_keys.append(chapter_url)
            urls = _chapter_page_urls(chapter_url, page)
            pages = []
            for i, image_url in enumerate(urls, 1):
                pages.append(_get(image_url, referer=referer))
                if on_progress:
                    on_progress(n, i, len(urls))
            fetched.append((n, pages))
        return fetched

    if any(site in url for site in BROWSER_ONLY_SITES):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                fetched = _run(browser.new_page(user_agent=USER_AGENT))
            finally:
                browser.close()
    else:
        fetched = _run(None)

    cache = _load_common_hashes()
    all_data = [data for _, pages in fetched for data in pages]
    exact_hashes = [hashlib.sha1(data).hexdigest() for data in all_data]
    phashes = [_ahash(data) for data in all_data]
    chapter_of = [ci for ci, (_, pages) in enumerate(fetched) for _ in pages]
    filler = _find_filler(chapter_of, chapter_keys, exact_hashes, phashes, cache)
    COMMON_HASH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    COMMON_HASH_CACHE.write_text(json.dumps(cache), encoding="utf-8")

    chapters: list[FetchChapterResult] = []
    pos = 0
    for n, pages in fetched:
        prefix = f"c{n:03d}_" if count > 1 else ""
        out_i = skipped = 0
        for data in pages:
            if filler[pos]:
                skipped += 1
            else:
                out_i += 1
                (chapter_dir / f"{prefix}{out_i:03d}.jpg").write_bytes(data)
            pos += 1
        chapters.append(FetchChapterResult(n=n, saved=out_i, skipped=skipped))

    return FetchResult(
        total_saved=sum(c.saved for c in chapters),
        total_skipped=sum(c.skipped for c in chapters),
        chapters=chapters,
    )
