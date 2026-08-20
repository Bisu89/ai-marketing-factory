"""Task 07 -- Performance Intelligence, core layer: joins PublishLog
(creative metadata: platform/page/hook_type/story_style/affiliate) to
InsightPostSnapshot (real Meta performance numbers) via PublishLog's own
post_id/page_id link -- both core tables (app/models/*), so this stays a
plain service, no composition root needed. Pillar/Format breakdowns need
app.modules.content_strategy/ai.story, which this layer must never import
(app/modules/README.md: core never points out) -- those live in the
composition root, app/api/v1/endpoints/performance_intelligence.py.

Never stores a copy of any lifetime metric (views/interactions/etc.) --
every number here is resolved live from the latest InsightPostSnapshot on
every call, exactly like the pre-existing publish_log_service.py already
did for the single-log case. A PublishLog with no post_id/page_id (never
linked) or no matching snapshot yet always reports None for every
snapshot-derived field, never a fabricated 0 -- see VideoPerformance's own
docstring for why 0 and "no data" must stay distinguishable.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.models.publish_log import PublishLog
from app.services.insights.publish_log_service import all_snapshots_for, latest_snapshot_for

# Performance score weighting (see VideoPerformance.performance_score docstring)
# -- a documented ranking heuristic built from real inputs, not a platform
# value. Tunable here, in one place, if the weighting ever needs revisiting.
_SCORE_VIEWS_CAP = 100_000  # views at/above this contribute the max views component
_SCORE_VIEWS_WEIGHT = 60.0
_SCORE_ENGAGEMENT_WEIGHT = 40.0


@dataclass
class VideoPerformance:
    """One PublishLog's resolved performance. Every snapshot-derived field
    is `None` (not 0) when there is genuinely no data to compute it from --
    a video that really got 0 views (rare, but real) must stay
    distinguishable from a video nobody ever linked to a CSV upload.
    `*_note` fields exist specifically for this task's own "if a metric
    cannot be calculated reliably, return null and explain why" -- never
    silently blank.
    """

    publish_log_id: int
    video_id: int
    video_title: str
    platform: str
    page_name: str | None
    hook_type: str | None
    story_style: str | None
    published_at: datetime
    duration_sec: float | None  # from the linked snapshot if available, else Video.duration_sec
    linked: bool  # post_id/page_id set on the PublishLog at all

    views: int | None = None
    interactions: int | None = None
    comments: int | None = None
    shares: int | None = None
    reactions: int | None = None
    saves: int | None = None
    real_followers: int | None = None

    engagement_rate: float | None = None  # interactions / views
    share_rate: float | None = None  # shares / views -- Task 08's own required metric
    follower_conversion_rate: float | None = None  # real_followers / views

    view_velocity_per_day: float | None = None
    view_velocity_note: str | None = None

    # Task 08 -- "publication age if data supports it": views accumulated
    # per day since PublishLog.published_at (not the same thing as
    # view_velocity_per_day above, which is growth *between two
    # snapshots*; this is total performance normalized for how long the
    # post has simply been live).
    views_per_day_since_publish: float | None = None
    views_per_day_note: str | None = None

    # Task 08 -- "account/platform context": views expressed as a multiple
    # of this platform's own average linked views (1.0 = exactly average
    # for that platform), computed once the full performance list is
    # known -- see apply_platform_relative_views(). None until that runs,
    # or when the platform has too few linked samples to average
    # meaningfully.
    platform_relative_views: float | None = None
    platform_relative_note: str | None = None

    performance_score: float | None = None
    performance_score_note: str | None = None

    data_note: str | None = None  # set when linked=False or no snapshot found yet


def _compute_performance(log: PublishLog, db: Session) -> VideoPerformance:
    perf = VideoPerformance(
        publish_log_id=log.id,
        video_id=log.video_id,
        video_title=log.video.title,
        platform=log.platform,
        page_name=log.page_name,
        hook_type=log.hook_type,
        story_style=log.story_style,
        published_at=log.published_at,
        duration_sec=log.video.duration_sec,  # snapshot's own duration_sec (if linked) overrides below
        linked=bool(log.post_id and log.page_id),
    )

    if not perf.linked:
        perf.data_note = "Chưa gắn với dữ liệu Insights (post_id/page_id) -- không có số liệu thật để tính."
        return perf

    snapshot = latest_snapshot_for(db, log.post_id, log.page_id)
    if snapshot is None:
        perf.data_note = "Đã gắn post_id/page_id nhưng chưa có snapshot Insights nào khớp -- có thể upload đã bị xoá."
        return perf

    if snapshot.duration_sec:
        perf.duration_sec = snapshot.duration_sec

    perf.views = snapshot.views
    perf.interactions = snapshot.interactions
    perf.comments = snapshot.comments
    perf.shares = snapshot.shares
    perf.reactions = snapshot.reactions
    perf.saves = snapshot.saves
    perf.real_followers = snapshot.real_followers

    if snapshot.views > 0:
        perf.engagement_rate = round(snapshot.interactions / snapshot.views, 4)
        perf.share_rate = round(snapshot.shares / snapshot.views, 5)
        perf.follower_conversion_rate = round(snapshot.real_followers / snapshot.views, 5)
    else:
        perf.data_note = "Snapshot có 0 views -- engagement/share rate/follower conversion không tính được (chia cho 0)."

    # Publication-age normalization: views accrued per day since the post
    # actually went live, measured up to when this snapshot's own upload
    # was taken (not "now" -- that would make the same historical snapshot
    # report a different rate every time this endpoint is called later).
    latest_upload_at = snapshot.upload.uploaded_at
    published_at = log.published_at
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    if latest_upload_at.tzinfo is None:
        latest_upload_at = latest_upload_at.replace(tzinfo=timezone.utc)
    days_live = (latest_upload_at - published_at).total_seconds() / 86400
    if days_live <= 0:
        perf.views_per_day_note = "Ngày đăng (published_at) không sớm hơn thời điểm snapshot -- không tính được views/ngày."
    else:
        perf.views_per_day_since_publish = round(snapshot.views / days_live, 1)

    # View velocity needs at least 2 real, dated snapshots to measure a
    # rate of change -- a single snapshot is only a static total, not a
    # trend. See docstring: this is exactly the "if data doesn't support
    # it, return null and explain why" case the task calls out by name.
    history = all_snapshots_for(db, log.post_id, log.page_id)
    if len(history) < 2:
        perf.view_velocity_note = (
            f"Chỉ có {len(history)} snapshot cho bài đăng này -- cần ít nhất 2 lần upload CSV theo thời gian "
            "để tính tốc độ tăng view."
        )
    else:
        first, latest_snap = history[0], history[-1]
        days = (latest_snap.upload.uploaded_at - first.upload.uploaded_at).total_seconds() / 86400
        if days <= 0:
            perf.view_velocity_note = "Hai snapshot có cùng thời điểm upload -- không tính được tốc độ theo ngày."
        else:
            perf.view_velocity_per_day = round((latest_snap.views - first.views) / days, 1)

    # Performance score: a deliberate, documented ranking heuristic (never
    # presented as a platform-provided number) -- 60% a capped views
    # component, 40% engagement rate scaled to the same 0-100 range. Only
    # computed when views is a real number; never invented from partial data.
    views_component = min(perf.views, _SCORE_VIEWS_CAP) / _SCORE_VIEWS_CAP * _SCORE_VIEWS_WEIGHT
    engagement_component = (perf.engagement_rate or 0) * _SCORE_ENGAGEMENT_WEIGHT
    perf.performance_score = round(views_component + engagement_component, 2)
    perf.performance_score_note = (
        f"Heuristic nội bộ: {_SCORE_VIEWS_WEIGHT:.0f}% views (cap ở {_SCORE_VIEWS_CAP:,}) "
        f"+ {_SCORE_ENGAGEMENT_WEIGHT:.0f}% engagement rate -- không phải số liệu do nền tảng cung cấp."
    )

    return perf


_MIN_SAMPLES_FOR_PLATFORM_BASELINE = 2


def apply_platform_relative_views(performances: list[VideoPerformance]) -> None:
    """Task 08 -- "account/platform context" normalization: a raw view
    count means something different on every platform (algorithm reach,
    typical audience size), so comparing raw views across platforms isn't
    a fair ranking. Expresses each linked video's views as a multiple of
    its *own platform's* average linked views instead -- 1.8 means "1.8x
    this platform's own average," comparable across platforms in a way
    raw counts aren't. Mutates the list in place (called once, right
    after all_performances() builds it) rather than returning a copy.
    """
    by_platform: dict[str, list[VideoPerformance]] = {}
    for p in performances:
        if p.views is not None:
            by_platform.setdefault(p.platform, []).append(p)

    platform_avg = {
        platform: sum(p.views for p in items) / len(items)
        for platform, items in by_platform.items()
        if len(items) >= _MIN_SAMPLES_FOR_PLATFORM_BASELINE
    }

    for p in performances:
        if p.views is None:
            continue
        avg = platform_avg.get(p.platform)
        if avg is None or avg == 0:
            linked_count = len(by_platform.get(p.platform, []))
            p.platform_relative_note = (
                f"Chỉ có {linked_count} video đã gắn dữ liệu trên nền tảng '{p.platform}' -- cần ít nhất "
                f"{_MIN_SAMPLES_FOR_PLATFORM_BASELINE} để tính baseline trung bình của nền tảng."
            )
            continue
        p.platform_relative_views = round(p.views / avg, 3)


@dataclass
class DimensionPerformance:
    """One group (a hook_type, a story_style, a platform, ...) with
    aggregated performance across every PublishLog in that group that has
    real linked data. `sample_size` is how many PublishLogs contributed --
    always shown so a "top hook" based on 1 real post isn't mistaken for
    one based on 20.
    """

    label: str
    sample_size: int
    linked_sample_size: int
    total_views: int | None
    avg_views: float | None
    avg_engagement_rate: float | None
    note: str | None = None


def group_performances_by(performances: list[VideoPerformance], key_fn, label_fn) -> list[DimensionPerformance]:
    """Standalone so the composition root (performance_intelligence.py) can
    reuse the exact same grouping/sorting logic for Top Pillars/Top
    Formats, which need a `key_fn` resolved from ai.story/content_strategy
    (pillar/format names) -- this function itself stays core-only, it just
    doesn't insist on producing its own VideoPerformance list.
    """
    groups: dict[str, list[VideoPerformance]] = {}
    for p in performances:
        key = key_fn(p)
        if key is None:
            continue
        groups.setdefault(key, []).append(p)

    results = []
    for key, items in groups.items():
        linked = [p for p in items if p.views is not None]
        if linked:
            total_views = sum(p.views for p in linked)
            results.append(
                DimensionPerformance(
                    label=label_fn(key),
                    sample_size=len(items),
                    linked_sample_size=len(linked),
                    total_views=total_views,
                    avg_views=round(total_views / len(linked), 1),
                    avg_engagement_rate=(
                        round(sum(p.engagement_rate for p in linked if p.engagement_rate is not None) / len(linked), 4)
                        if any(p.engagement_rate is not None for p in linked)
                        else None
                    ),
                )
            )
        else:
            results.append(
                DimensionPerformance(
                    label=label_fn(key),
                    sample_size=len(items),
                    linked_sample_size=0,
                    total_views=None,
                    avg_views=None,
                    avg_engagement_rate=None,
                    note=f"{len(items)} lượt đăng dùng '{label_fn(key)}' nhưng chưa lượt nào gắn dữ liệu Insights thật.",
                )
            )
    results.sort(key=lambda d: (d.total_views is None, -(d.total_views or 0)))
    return results[:20]


class PerformanceService:
    def __init__(self, db: Session):
        self.db = db

    def _all_logs(self) -> list[PublishLog]:
        return self.db.query(PublishLog).options(selectinload(PublishLog.video)).order_by(PublishLog.published_at.desc()).all()

    def all_performances(self) -> list[VideoPerformance]:
        """Public -- the composition root (performance_intelligence.py)
        reuses this list to add pillar/format (which needs ai.story +
        content_strategy, so it can't be computed inside this core-only
        service) without a second, duplicate query pass over PublishLog.
        """
        performances = [_compute_performance(log, self.db) for log in self._all_logs()]
        apply_platform_relative_views(performances)
        return performances

    # -- 1. Top videos --------------------------------------------------

    def top_videos(self, limit: int = 10) -> list[VideoPerformance]:
        performances = self.all_performances()
        # Linked-with-a-real-score entries first (highest score first),
        # unlinked/no-data entries after (in their existing recency
        # order) -- never silently dropped, per "do not silently discard".
        scored = [p for p in performances if p.performance_score is not None]
        unscored = [p for p in performances if p.performance_score is None]
        scored.sort(key=lambda p: p.performance_score, reverse=True)
        return (scored + unscored)[:limit]

    # -- 2. Top hooks -----------------------------------------------------

    def top_hooks(self) -> list[DimensionPerformance]:
        return group_performances_by(self.all_performances(), lambda p: p.hook_type, lambda k: k)

    # -- 3. Top story styles -----------------------------------------------

    def top_story_styles(self) -> list[DimensionPerformance]:
        return group_performances_by(self.all_performances(), lambda p: p.story_style, lambda k: k)

    # -- 6. Performance by platform -----------------------------------------

    def by_platform(self) -> list[DimensionPerformance]:
        return group_performances_by(self.all_performances(), lambda p: p.platform, lambda k: k)
