"""Rule-based viral score (brief sections 9-14). NO AI, NO API -- every
number is derived locally from metadata already fetched during search.

The score exists only to *rank* results. Each component returns 0-100 and
missing data degrades gracefully (a component that can't be computed is
dropped and the remaining weights are renormalized, so a video isn't
punished for a platform simply not exposing a metric).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.modules.discovery.contracts import VideoResult

# -- Config (brief: "make this configurable") -------------------------

WEIGHTS = {
    "views": 0.30,
    "engagement": 0.25,
    "recency": 0.15,
    "relevance": 0.15,
    "short_form": 0.10,
    "content_signals": 0.05,
}

# Recency buckets: max age in days -> score.
RECENCY_BUCKETS = ((7, 100.0), (30, 80.0), (90, 55.0), (365, 30.0))
RECENCY_FLOOR = 10.0

# Short-form sweet spot in seconds.
SHORT_FORM_IDEAL = (10, 90)
SHORT_FORM_ACCEPTABLE_MAX = 180

# Views are compressed with log10 so a 10M-view video doesn't obliterate a
# smaller-but-hot one (brief section 9). 1e7 views -> 100.
VIEWS_LOG_CEILING = 7.0

# Content signal words (brief section 14). A hit in title/description/tags
# adds a small bonus, capped.
CONTENT_SIGNAL_WORDS = (
    "before", "after", "transformation", "makeover", "reveal", "reaction",
    "reacts", "shocked", "surprise", "surprised", "emotional", "wholesome",
    "unexpected", "wife", "husband", "girlfriend", "boyfriend", "beard",
    "shave", "family", "brother", "sister", "mom", "dad", "son", "daughter",
    "rescue", "glow up", "glowup", "does not recognize", "didn't recognize",
    "first time", "results", "journey",
)

_WORD_RE = re.compile(r"[a-z0-9']+")


@dataclass
class ScoreConfig:
    weights: dict[str, float]
    recency_buckets: tuple[tuple[int, float], ...] = RECENCY_BUCKETS
    short_form_ideal: tuple[int, int] = SHORT_FORM_IDEAL

    @classmethod
    def default(cls) -> ScoreConfig:
        return cls(weights=dict(WEIGHTS))


def _tokens(*texts: str | None) -> list[str]:
    joined = " ".join(t.lower() for t in texts if t)
    return _WORD_RE.findall(joined)


# -- Individual components -------------------------------------------


def views_score(v: VideoResult) -> float | None:
    if v.views is None:
        return None
    if v.views <= 0:
        return 0.0
    return min(100.0, math.log10(v.views + 1) / VIEWS_LOG_CEILING * 100.0)


def engagement_score(v: VideoResult) -> float | None:
    rate = v.engagement_rate
    if rate is None:
        return None
    # A 10% engagement rate is exceptional for video -> 100. Linear below.
    return max(0.0, min(100.0, rate / 0.10 * 100.0))


def recency_score(v: VideoResult, cfg: ScoreConfig) -> float | None:
    if v.published_at is None:
        return None
    published = v.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - published).total_seconds() / 86400
    age_days = max(age_days, 0)
    for max_days, score in cfg.recency_buckets:
        if age_days <= max_days:
            return score
    return RECENCY_FLOOR


def relevance_score(v: VideoResult, query_terms: list[str]) -> float:
    """Local keyword overlap (brief section 12) -- no TF-IDF needed for V1.

    Fraction of distinct query terms that appear in the result's
    title/description/tags/creator, with the title weighted double.
    """
    if not query_terms:
        return 50.0
    haystack_title = set(_tokens(v.title))
    haystack_rest = set(_tokens(v.description, " ".join(v.content_tags), v.creator_name))
    hits = 0.0
    possible = 0.0
    for term in {t.lower() for t in query_terms if t}:
        possible += 2.0
        if term in haystack_title:
            hits += 2.0
        elif term in haystack_rest:
            hits += 1.0
    if possible == 0:
        return 50.0
    return round(hits / possible * 100.0, 1)


def short_form_score(v: VideoResult, cfg: ScoreConfig) -> float | None:
    dur = v.duration_sec
    ar = v.aspect_ratio

    dur_component: float | None = None
    if dur is not None:
        lo, hi = cfg.short_form_ideal
        if lo <= dur <= hi:
            dur_component = 100.0
        elif dur < lo:
            dur_component = 60.0
        elif dur <= SHORT_FORM_ACCEPTABLE_MAX:
            dur_component = 70.0
        else:
            # Longer videos are NOT rejected (brief section 13), just lower.
            dur_component = max(20.0, 70.0 - (dur - SHORT_FORM_ACCEPTABLE_MAX) / 60.0)

    ar_component: float | None = None
    if ar is not None:
        # 9:16 == 0.5625. Vertical -> high, square -> mid, landscape -> low.
        if ar <= 0.65:
            ar_component = 100.0
        elif ar < 1.0:
            ar_component = 75.0
        elif ar <= 1.05:
            ar_component = 55.0
        else:
            ar_component = 30.0

    parts = [c for c in (dur_component, ar_component) if c is not None]
    if not parts:
        return None
    return round(sum(parts) / len(parts), 1)


def content_signal_score(v: VideoResult) -> float:
    haystack = " ".join(
        p.lower() for p in (v.title, v.description or "", " ".join(v.content_tags)) if p
    )
    if not haystack:
        return 0.0
    hits = sum(1 for w in CONTENT_SIGNAL_WORDS if w in haystack)
    return min(100.0, hits * 25.0)


def detect_content_tags(v: VideoResult) -> list[str]:
    """Cheap title/description/tag signal detection (brief section 14),
    stored on the result for the card + "find more like this"."""
    haystack = " ".join(
        p.lower() for p in (v.title, v.description or "", " ".join(v.content_tags)) if p
    )
    found = [w for w in CONTENT_SIGNAL_WORDS if w in haystack]
    # Keep the engine-supplied tags (hashtags, subreddit) and merge.
    merged = list(dict.fromkeys([*v.content_tags, *found]))
    return merged[:12]


# -- Composite ------------------------------------------------------


def score_result(v: VideoResult, query_terms: list[str], cfg: ScoreConfig | None = None) -> VideoResult:
    cfg = cfg or ScoreConfig.default()

    v.content_tags = detect_content_tags(v)

    components: dict[str, float | None] = {
        "views": views_score(v),
        "engagement": engagement_score(v),
        "recency": recency_score(v, cfg),
        "relevance": relevance_score(v, query_terms),
        "short_form": short_form_score(v, cfg),
        "content_signals": content_signal_score(v),
    }

    # Renormalize weights over the components we could actually compute.
    available = {k: s for k, s in components.items() if s is not None}
    total_weight = sum(cfg.weights[k] for k in available) or 1.0
    viral = sum(available[k] * cfg.weights[k] for k in available) / total_weight

    v.relevance_score = components["relevance"] or 0.0
    v.engagement_score = components["engagement"] or 0.0
    v.recency_score = components["recency"] or 0.0
    v.short_form_score = components["short_form"] or 0.0
    v.content_signal_score = components["content_signals"] or 0.0
    v.viral_score = round(viral, 1)
    return v


def score_all(results: list[VideoResult], query_terms: list[str], cfg: ScoreConfig | None = None) -> list[VideoResult]:
    cfg = cfg or ScoreConfig.default()
    return [score_result(v, query_terms, cfg) for v in results]
