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
running.
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
from collections import Counter
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


def _cluster_phashes(phashes: list[str | None]) -> list[int]:
    """Groups this run's pages into near-duplicate buckets (Hamming <=
    PHASH_MAX_DIST of the bucket's first member). Returns, per page, the
    size of its bucket (1 for a None hash or a bucket of its own) -- >1
    means the same image recurred within this run."""
    reps: list[str] = []          # one representative hash per bucket
    counts: list[int] = []
    bucket_of: list[int | None] = []
    for ph in phashes:
        if ph is None:
            bucket_of.append(None)
            continue
        match = next((b for b, rep in enumerate(reps) if _hamming(ph, rep) <= PHASH_MAX_DIST), None)
        if match is None:
            reps.append(ph)
            counts.append(1)
            bucket_of.append(len(reps) - 1)
        else:
            counts[match] += 1
            bucket_of.append(match)
    return [1 if b is None else counts[b] for b in bucket_of]


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

    def _run(page) -> list[tuple[int | None, list[bytes]]]:
        fetched: list[tuple[int | None, list[bytes]]] = []
        for k in range(count):
            n = int(match.group(1)) + k if match else None
            chapter_url = url if k == 0 else url[:match.start(1)] + str(n) + url[match.end(1):]
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
    exact_tally = Counter(exact_hashes)
    run_bucket_sizes = _cluster_phashes(phashes)

    # A page is filler if its exact hash, or a near-duplicate perceptual hash
    # (recompressed/re-scaled copy of the same image), was already flagged in
    # a past fetch call (cache) or recurs within this run.
    filler = []
    for h, ph, bucket_size in zip(exact_hashes, phashes, run_bucket_sizes):
        exact_hit = cache["exact"].get(h, 0) > 0 or exact_tally[h] > 1
        phash_hit = ph is not None and (bucket_size > 1 or _closest_phash(ph, cache["phash"]) is not None)
        filler.append(exact_hit or phash_hit)
        cache["exact"][h] = cache["exact"].get(h, 0) + 1
        if ph is not None:
            hit = _closest_phash(ph, cache["phash"])  # fold near-dups into one cache key, don't grow unbounded
            cache["phash"][hit or ph] = cache["phash"].get(hit or ph, 0) + 1
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
