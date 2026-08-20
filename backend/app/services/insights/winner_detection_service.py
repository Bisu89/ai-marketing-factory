"""Task 08 -- Content Winner Detection: statistically-aware grouping on
top of Task 07's PerformanceService.all_performances() -- reuses that
single source of truth for every number (views/engagement/share rate/
follower conversion/performance_score/platform_relative_views), never
re-derives them. Core-only (hook/story_style/platform/duration groupings
only need PublishLog + Video, both core) -- pillar/format grouping needs
ai.story/content_strategy, so it's assembled in the composition root
(app/api/v1/endpoints/winner_detection.py), same split as Task 07's own
Top Pillars/Top Formats.

"Do not simply rank by raw views": WinnerGroupStats.performance_score
below is built from platform_relative_views (Task 07's own "how many
times this platform's own average" normalization) + engagement_rate, not
raw view counts -- see _group_score_component. A group whose members'
platform baselines aren't computable yet (too few linked samples on that
platform) falls back to the member's own (raw-views-based)
performance_score, and that fallback is stated in the group's `note`,
never silently swapped in.

"Do not call something a winner with one video only": every WinnerGroupStats
carries `meets_minimum_sample`/`confidence`, computed from a caller-supplied
`min_sample_size` (default 5, per this task's own example) -- callers are
expected to gate "winner" language on `meets_minimum_sample`, not just
sort and take the top of the list.
"""

import statistics
from dataclasses import dataclass

from app.services.insights.performance_service import VideoPerformance

# Reuses app.services.library.repository.DURATION_BUCKETS' own bucket
# definition exactly (same labels/ranges the Library page's own duration
# filter already uses) rather than inventing a second bucketing scheme.
from app.services.library.repository import DURATION_BUCKETS

DEFAULT_MIN_SAMPLE_SIZE = 5


def _duration_bucket(duration_sec: float | None) -> str | None:
    if duration_sec is None:
        return None
    for label, (low, high) in DURATION_BUCKETS.items():
        if (low is None or duration_sec >= low) and (high is None or duration_sec < high):
            return label
    return None


@dataclass
class WinnerGroupStats:
    """One group's full statistical picture -- every field Task 08's own
    "Output" section asks for, plus the confidence/eligibility fields
    needed to keep "winner" claims honest.
    """

    dimension: str  # "pillar" | "format" | "hook" | "story_style" | "platform" | "duration"
    label: str

    sample_size: int  # every PublishLog in the group, linked or not
    linked_sample_size: int  # PublishLogs with real snapshot data
    min_sample_size: int  # the threshold this group was evaluated against
    meets_minimum_sample: bool
    confidence: str  # "insufficient" | "low" | "medium" | "high"

    avg_views: float | None
    median_views: float | None
    avg_engagement_rate: float | None
    avg_share_rate: float | None
    avg_follower_conversion_rate: float | None
    avg_views_per_day_since_publish: float | None

    performance_score: float | None
    performance_score_basis: str  # explains exactly what performance_score above is built from
    note: str | None = None


def _confidence(linked_sample_size: int, min_sample_size: int) -> str:
    if linked_sample_size < min_sample_size:
        return "insufficient"
    if linked_sample_size < min_sample_size * 2:
        return "low"
    if linked_sample_size < min_sample_size * 4:
        return "medium"
    return "high"


def _group_score_component(p: VideoPerformance) -> float | None:
    """60% platform-relative views (capped at 3x that platform's own
    average, so one viral outlier can't single-handedly carry a group)
    + 40% engagement rate -- see module docstring. Falls back to the
    video's own (raw-views-based) performance_score when platform_relative_views
    isn't computable yet (that platform has too few linked samples).
    """
    if p.performance_score is None:
        return None
    if p.platform_relative_views is None:
        return p.performance_score
    views_component = min(p.platform_relative_views, 3.0) / 3.0 * 60.0
    engagement_component = (p.engagement_rate or 0) * 40.0
    return round(views_component + engagement_component, 2)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def compute_group_stats(
    performances: list[VideoPerformance],
    key_fn,
    label_fn,
    dimension: str,
    min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
) -> list[WinnerGroupStats]:
    groups: dict[str, list[VideoPerformance]] = {}
    for p in performances:
        key = key_fn(p)
        if key is None:
            continue
        groups.setdefault(key, []).append(p)

    results = []
    for key, items in groups.items():
        linked = [p for p in items if p.views is not None]
        confidence = _confidence(len(linked), min_sample_size)
        meets_minimum = len(linked) >= min_sample_size

        if not linked:
            results.append(
                WinnerGroupStats(
                    dimension=dimension, label=label_fn(key), sample_size=len(items), linked_sample_size=0,
                    min_sample_size=min_sample_size, meets_minimum_sample=False, confidence=confidence,
                    avg_views=None, median_views=None, avg_engagement_rate=None, avg_share_rate=None,
                    avg_follower_conversion_rate=None, avg_views_per_day_since_publish=None,
                    performance_score=None, performance_score_basis="Không có dữ liệu Insights nào được gắn cho nhóm này.",
                    note=f"{len(items)} video thuộc nhóm '{label_fn(key)}' nhưng chưa video nào gắn dữ liệu Insights thật.",
                )
            )
            continue

        views_list = [p.views for p in linked]
        scores = [s for s in (_group_score_component(p) for p in linked) if s is not None]
        used_fallback = any(p.platform_relative_views is None for p in linked if p.performance_score is not None)

        note = None
        if not meets_minimum:
            note = (
                f"Chỉ {len(linked)} video có dữ liệu thật (cần tối thiểu {min_sample_size}) -- "
                "chưa đủ căn cứ để gọi đây là 'winner'."
            )
        elif used_fallback:
            note = "Một số video trong nhóm dùng performance_score gốc (views thô) do chưa đủ dữ liệu để chuẩn hoá theo nền tảng."

        results.append(
            WinnerGroupStats(
                dimension=dimension,
                label=label_fn(key),
                sample_size=len(items),
                linked_sample_size=len(linked),
                min_sample_size=min_sample_size,
                meets_minimum_sample=meets_minimum,
                confidence=confidence,
                avg_views=round(statistics.mean(views_list), 1),
                median_views=round(statistics.median(views_list), 1),
                avg_engagement_rate=_avg([p.engagement_rate for p in linked if p.engagement_rate is not None]),
                avg_share_rate=_avg([p.share_rate for p in linked if p.share_rate is not None]),
                avg_follower_conversion_rate=_avg(
                    [p.follower_conversion_rate for p in linked if p.follower_conversion_rate is not None]
                ),
                avg_views_per_day_since_publish=_avg(
                    [p.views_per_day_since_publish for p in linked if p.views_per_day_since_publish is not None]
                ),
                performance_score=round(statistics.mean(scores), 2) if scores else None,
                performance_score_basis=(
                    "Trung bình 60% views chuẩn hoá theo nền tảng (cap 3x trung bình nền tảng) + 40% engagement rate."
                ),
                note=note,
            )
        )

    results.sort(key=lambda g: (g.performance_score is None, -(g.performance_score or 0)))
    return results


def key_by_duration(p: VideoPerformance) -> str | None:
    return _duration_bucket(p.duration_sec)


@dataclass
class TrendGroupStats:
    """Rising/underperforming verdict for one group, built by comparing
    the group's own performance_score in the earlier vs. more recent half
    of its members' published_at dates -- a real trend needs a real time
    split, so this is None/"insufficient_data" whenever either half can't
    meet min_sample_size on its own, rather than guessing from too little
    data.
    """

    dimension: str
    label: str
    trend: str  # "rising" | "underperforming" | "stable" | "insufficient_data"
    earlier_avg_score: float | None
    recent_avg_score: float | None
    change_pct: float | None
    note: str


_RISING_THRESHOLD_PCT = 15.0  # relative change needed to call it a real trend, not noise


def compute_trends(
    performances: list[VideoPerformance],
    key_fn,
    label_fn,
    dimension: str,
    min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
) -> list[TrendGroupStats]:
    groups: dict[str, list[VideoPerformance]] = {}
    for p in performances:
        key = key_fn(p)
        if key is None or p.views is None:
            continue
        groups.setdefault(key, []).append(p)

    # Halving needs at least min_sample_size *per half* to mean anything --
    # smaller than that and "earlier" vs "recent" is just noise from 1-2 posts.
    half_threshold = max(2, min_sample_size // 2)

    results = []
    for key, items in groups.items():
        label = label_fn(key)
        ordered = sorted(items, key=lambda p: p.published_at)
        mid = len(ordered) // 2
        earlier, recent = ordered[:mid], ordered[mid:]

        if len(earlier) < half_threshold or len(recent) < half_threshold:
            results.append(
                TrendGroupStats(
                    dimension=dimension, label=label, trend="insufficient_data",
                    earlier_avg_score=None, recent_avg_score=None, change_pct=None,
                    note=(
                        f"Cần tối thiểu {half_threshold} video ở mỗi nửa thời gian (đầu/gần đây) để đánh giá xu hướng -- "
                        f"hiện có {len(earlier)} và {len(recent)}."
                    ),
                )
            )
            continue

        earlier_scores = [s for s in (_group_score_component(p) for p in earlier) if s is not None]
        recent_scores = [s for s in (_group_score_component(p) for p in recent) if s is not None]
        if not earlier_scores or not recent_scores:
            results.append(
                TrendGroupStats(
                    dimension=dimension, label=label, trend="insufficient_data",
                    earlier_avg_score=None, recent_avg_score=None, change_pct=None,
                    note="Không đủ video có performance_score ở một trong hai nửa thời gian.",
                )
            )
            continue

        earlier_avg = statistics.mean(earlier_scores)
        recent_avg = statistics.mean(recent_scores)
        change_pct = round((recent_avg - earlier_avg) / earlier_avg * 100, 1) if earlier_avg > 0 else None

        if change_pct is None:
            trend = "insufficient_data"
            note = "Điểm hiệu suất trung bình ở nửa đầu là 0 -- không tính được % thay đổi."
        elif change_pct >= _RISING_THRESHOLD_PCT:
            trend = "rising"
            note = f"Điểm hiệu suất trung bình tăng {change_pct:+.1f}% giữa nửa đầu và nửa gần đây."
        elif change_pct <= -_RISING_THRESHOLD_PCT:
            trend = "underperforming"
            note = f"Điểm hiệu suất trung bình giảm {change_pct:+.1f}% giữa nửa đầu và nửa gần đây."
        else:
            trend = "stable"
            note = f"Thay đổi {change_pct:+.1f}% -- trong ngưỡng biến động bình thường (dưới {_RISING_THRESHOLD_PCT:.0f}%)."

        results.append(
            TrendGroupStats(
                dimension=dimension, label=label, trend=trend,
                earlier_avg_score=round(earlier_avg, 2), recent_avg_score=round(recent_avg, 2),
                change_pct=change_pct, note=note,
            )
        )

    return results
