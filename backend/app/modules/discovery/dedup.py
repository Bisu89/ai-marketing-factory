"""Cross-platform deduplication (brief section 16).

The same clip is routinely reposted to Reddit / YouTube / TikTok / IG. We
group results that are "the same video" so the grid shows one card
("also on: TikTok, Reddit") instead of three unrelated-looking rows.

Signals used (all local, no thumbnail hashing in V1):
  - identical normalized source URL
  - same creator handle + high title similarity
  - very high title similarity alone (>= TITLE_DUP_THRESHOLD)
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.modules.discovery.contracts import VideoResult

TITLE_DUP_THRESHOLD = 0.82
TITLE_WITH_CREATOR_THRESHOLD = 0.6

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "my", "me", "i", "he", "she", "it", "this", "that", "is", "was", "at",
    "by", "from", "reddit", "shorts", "short", "video", "tiktok", "youtube",
    # auxiliary / negation -- platforms rephrase these when reposting
    # ("does not" vs "doesn't"), so they must not block a dedup match.
    "not", "no", "do", "does", "did", "doesnt", "dont", "didnt", "has",
    "have", "had", "will", "just", "so", "as", "but", "when", "after",
    "before", "you", "your",
}
_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_url(url: str) -> str:
    """Strip scheme, www, query, trailing slash, lower-case host."""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url.strip().lower()
    host = (p.netloc or "").lower().removeprefix("www.")
    path = (p.path or "").rstrip("/")
    return f"{host}{path}".lower()


def _title_tokens(title: str) -> set[str]:
    collapsed = title.lower().replace("'", "").replace("’", "")
    return {w for w in _WORD_RE.findall(collapsed) if w not in _STOPWORDS and len(w) > 1}


def title_similarity(a: str, b: str) -> float:
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union


def _same_creator(a: VideoResult, b: VideoResult) -> bool:
    if not a.creator_name or not b.creator_name:
        return False
    na = a.creator_name.lower().lstrip("@").strip()
    nb = b.creator_name.lower().lstrip("@").strip()
    return bool(na) and na == nb


def _is_duplicate(a: VideoResult, b: VideoResult) -> bool:
    if a.source_url and b.source_url and normalize_url(a.source_url) == normalize_url(b.source_url):
        return True
    sim = title_similarity(a.title, b.title)
    if sim >= TITLE_DUP_THRESHOLD:
        return True
    if sim >= TITLE_WITH_CREATOR_THRESHOLD and _same_creator(a, b):
        return True
    return False


def deduplicate(results: list[VideoResult]) -> list[VideoResult]:
    """Return the surviving representative of each group (highest viral
    score wins), with `also_on` listing the other platforms it appeared on.
    The losers are dropped from the returned list.

    Runs after scoring so "highest viral score" is meaningful.
    """
    groups: list[list[VideoResult]] = []
    for r in results:
        placed = False
        for group in groups:
            if any(_is_duplicate(r, member) for member in group):
                group.append(r)
                placed = True
                break
        if not placed:
            groups.append([r])

    survivors: list[VideoResult] = []
    for group in groups:
        group.sort(key=lambda v: v.viral_score, reverse=True)
        rep = group[0]
        others = group[1:]
        rep.also_on = sorted({o.platform for o in others if o.platform != rep.platform})
        survivors.append(rep)
    return survivors
