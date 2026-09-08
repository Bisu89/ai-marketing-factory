"""Deterministic keyword expansion (brief section 8) -- NO AI.

A user query is expanded into a small set of related search strings by:
  1. matching the query against a hand-built topic dictionary, and
  2. always keeping the original query first.

The dictionary is a plain module constant -- the user never sees or manages
it. Keep the expansion small (<= MAX_EXPANSIONS) so YouTube's per-search
quota cost stays bounded (each extra query is another `search.list` call).
"""

from __future__ import annotations

import re

MAX_EXPANSIONS = 8

# topic key -> (trigger words, expansion phrases). A query matches a topic
# when any trigger word appears in it as a whole word.
TOPIC_DICTIONARY: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "beard": (
        ("beard", "shave", "stubble", "moustache", "mustache"),
        (
            "beard transformation",
            "beard shave",
            "beard makeover",
            "clean shave",
            "beard before after",
            "shaving reaction",
            "wife reacts beard",
            "man looks younger after shave",
        ),
    ),
    "haircut": (
        ("haircut", "hairstyle", "hair transformation", "barber"),
        (
            "haircut transformation",
            "hair makeover",
            "barber transformation",
            "before after haircut",
            "buzzcut reaction",
        ),
    ),
    "couple": (
        ("couple", "wife", "husband", "girlfriend", "boyfriend", "fiance", "fiancee"),
        (
            "wife reaction",
            "girlfriend reaction",
            "husband surprise",
            "couple surprise",
            "partner does not recognize",
        ),
    ),
    "family": (
        ("family", "brother", "sister", "mom", "mother", "dad", "father", "son", "daughter", "parent"),
        (
            "family reaction",
            "brother protects sister",
            "parent surprise",
            "mother son moment",
            "emotional family reunion",
        ),
    ),
    "funny": (
        ("funny", "hilarious", "prank", "fail", "blooper"),
        (
            "funny reaction",
            "unexpected reaction",
            "funny moment",
            "unexpected ending",
            "caught on camera funny",
        ),
    ),
    "transformation": (
        ("transformation", "makeover", "glow up", "glowup", "before after", "before and after"),
        (
            "body transformation",
            "makeover reveal",
            "glow up transformation",
            "before after reveal",
            "dramatic transformation",
        ),
    ),
    "weightloss": (
        ("weight loss", "weightloss", "lost weight", "fat loss", "body transformation"),
        (
            "weight loss transformation",
            "100 pound weight loss",
            "body transformation reveal",
            "fitness transformation",
        ),
    ),
    "makeup": (
        ("makeup", "make up", "makeover", "cosmetic"),
        (
            "makeup transformation",
            "no makeup to full glam",
            "makeover reveal",
            "power of makeup",
        ),
    ),
    "pet": (
        ("dog", "puppy", "cat", "kitten", "pet", "rescue dog"),
        (
            "rescue dog transformation",
            "dog reaction",
            "before after rescue",
            "pet reunion",
        ),
    ),
    "renovation": (
        ("renovation", "makeover", "diy", "restoration", "restore", "cleanup", "clean up"),
        (
            "room makeover",
            "house renovation before after",
            "restoration transformation",
            "deep clean transformation",
        ),
    ),
}

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def normalize_query(query: str) -> str:
    """Lower-cased, whitespace-collapsed. Used as the cache key component
    and for topic matching."""
    return " ".join(query.lower().split())


def expand_query(query: str, *, limit: int = MAX_EXPANSIONS) -> list[str]:
    """Return [original, ...related], de-duplicated, at most `limit` items.

    Deterministic: the same query always yields the same list in the same
    order (original first, then dictionary order, then phrase order).
    """
    original = normalize_query(query)
    if not original:
        return []

    query_words = _tokens(original)
    # Also treat the raw string for multi-word triggers ("before after").
    lowered = original

    out: list[str] = [original]
    seen = {original}

    for _topic, (triggers, phrases) in TOPIC_DICTIONARY.items():
        matched = any(
            (" " in trig and trig in lowered) or (trig in query_words)
            for trig in triggers
        )
        if not matched:
            continue
        for phrase in phrases:
            p = normalize_query(phrase)
            if p not in seen:
                out.append(p)
                seen.add(p)
            if len(out) >= limit:
                return out

    return out[:limit]


def keywords_from_result(title: str, tags: list[str], description: str | None = None) -> list[str]:
    """"Find more like this" (brief section 25) without AI: pull the topic
    expansions triggered by the selected video's own text, falling back to
    its content tags and salient title words.
    """
    text = " ".join(p for p in (title, description or "") if p)
    expanded = expand_query(text, limit=MAX_EXPANSIONS)
    # expand_query keeps `text` itself as element 0 -- drop it, it's a whole
    # sentence, not a search term.
    related = expanded[1:]
    if related:
        return related[:6]

    # No dictionary hit: use content tags, then the 4 longest title words.
    if tags:
        return tags[:6]
    words = sorted(_WORD_RE.findall(title.lower()), key=len, reverse=True)
    return list(dict.fromkeys(w for w in words if len(w) > 3))[:5]
