"""YouTube search engine -- YouTube Data API v3.

Needs an API key (APP_YOUTUBE_API_KEY); without one the engine reports
"unavailable" with a setup hint rather than failing the search.

Quota note (brief section 27): `search.list` costs 100 units against a
10,000/day free quota, so the orchestrator only ever hands this engine a
SMALL number of expanded queries. `videos.list` (1 unit / up to 50 ids)
backfills stats + duration + license that `search.list` doesn't return.

License handling (brief section 4):
  - videoLicense=creativeCommon  -> RIGHTS_CREATIVE_COMMONS + attribution
  - otherwise                    -> RIGHTS_STANDARD_PLATFORM_LICENSE
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.modules.discovery.contracts import (
    PLATFORM_YOUTUBE,
    RIGHTS_CREATIVE_COMMONS,
    RIGHTS_STANDARD_PLATFORM_LICENSE,
    EngineOutcome,
    VideoResult,
)
from app.modules.discovery.engines.base import BaseEngine, SearchOptions

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

_ISO8601_DURATION = re.compile(
    r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


def _parse_duration(iso: str | None) -> int | None:
    if not iso:
        return None
    m = _ISO8601_DURATION.fullmatch(iso)
    if not m:
        return None
    parts = {k: int(v) for k, v in m.groupdict(default="0").items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


class YouTubeEngine(BaseEngine):
    platform = PLATFORM_YOUTUBE

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None) -> None:
        self._client = client
        self._api_key_override = api_key

    def _api_key(self) -> str | None:
        return self._api_key_override or getattr(get_settings(), "youtube_api_key", None)

    def is_configured(self) -> bool:
        return bool(self._api_key())

    def unavailable_reason(self) -> str:
        return "Add a YouTube Data API key in Settings to search YouTube."

    def search(self, query: str, options: SearchOptions) -> EngineOutcome:
        key = self._api_key()
        if not key:
            return EngineOutcome.unavailable(self.platform, self.unavailable_reason())

        client = self._client or httpx.Client(follow_redirects=True)
        owns_client = self._client is None
        try:
            queries = options.queries or [query]
            by_id: dict[str, VideoResult] = {}
            published_after = None
            if options.max_age_days:
                cutoff = datetime.now(timezone.utc).timestamp() - options.max_age_days * 86400
                published_after = datetime.fromtimestamp(cutoff, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            quota_hit = False
            for q in queries:
                try:
                    for r in self._search_one(client, key, q, options, published_after):
                        by_id.setdefault(r.id, r)
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code if exc.response is not None else 0
                    reason = _error_reason(exc.response)
                    if status == 403:
                        # Quota exceeded / key disabled / API not enabled --
                        # stop hammering, keep whatever we already have.
                        quota_hit = reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded")
                        logger.warning("youtube: search.list 403 (%s) -- stopping", reason or "forbidden")
                        break
                    logger.warning("youtube: search.list %s (%s) for %r", status, reason, q)
                    continue

            if by_id:
                self._backfill(client, key, by_id)

            results = list(by_id.values())
            if results:
                # We have at least titles/thumbnails from search.list; the
                # scorers degrade gracefully when stats are missing.
                note = _QUOTA_MESSAGE if quota_hit else None
                return EngineOutcome(platform=self.platform, status="ok", results=results, error=note)
            if quota_hit:
                return EngineOutcome.unavailable(self.platform, _QUOTA_MESSAGE)
            return EngineOutcome.ok(self.platform, [])
        except httpx.HTTPStatusError as exc:
            reason = _error_reason(exc.response)
            if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
                return EngineOutcome.unavailable(self.platform, _QUOTA_MESSAGE)
            logger.warning("youtube: request failed (%s)", reason or exc)
            return EngineOutcome.failed(self.platform, "YouTube API rejected the request.")
        except httpx.HTTPError:
            logger.exception("youtube: network error")
            return EngineOutcome.failed(self.platform, "YouTube request failed (network error).")
        finally:
            if owns_client:
                client.close()

    def _search_one(
        self,
        client: httpx.Client,
        key: str,
        q: str,
        options: SearchOptions,
        published_after: str | None,
    ) -> list[VideoResult]:
        params = {
            "key": key,
            "part": "snippet",
            "q": q,
            "type": "video",
            "order": "relevance",
            "maxResults": str(min(options.limit_per_query, 25)),
            "safeSearch": "moderate",
        }
        if published_after:
            params["publishedAfter"] = published_after
        resp = client.get(_SEARCH_URL, params=params, timeout=20)
        resp.raise_for_status()
        out: list[VideoResult] = []
        for item in resp.json().get("items", []):
            vid = (item.get("id") or {}).get("videoId")
            snip = item.get("snippet") or {}
            if not vid:
                continue
            published = _parse_dt(snip.get("publishedAt"))
            thumbs = snip.get("thumbnails") or {}
            thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
            out.append(
                VideoResult(
                    platform=PLATFORM_YOUTUBE,
                    id=vid,
                    source_url=f"https://www.youtube.com/watch?v={vid}",
                    title=snip.get("title") or "Untitled",
                    description=snip.get("description") or None,
                    thumbnail_url=thumb,
                    creator_name=snip.get("channelTitle"),
                    creator_url=(
                        f"https://www.youtube.com/channel/{snip.get('channelId')}"
                        if snip.get("channelId")
                        else None
                    ),
                    published_at=published,
                    rights_status=RIGHTS_STANDARD_PLATFORM_LICENSE,
                )
            )
        return out

    def _backfill(self, client: httpx.Client, key: str, by_id: dict[str, VideoResult]) -> None:
        """Enrich search.list hits with stats/duration/license via videos.list
        (1 unit / 50 ids). A failure here is non-fatal -- the results stay,
        just without view counts etc. (the scorers handle missing metrics).
        """
        ids = list(by_id.keys())
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            params = {
                "key": key,
                "part": "statistics,contentDetails,status,snippet",
                "id": ",".join(chunk),
            }
            try:
                resp = client.get(_VIDEOS_URL, params=params, timeout=20)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                reason = _error_reason(getattr(exc, "response", None))
                logger.warning("youtube: videos.list backfill failed (%s) -- keeping bare results", reason or exc)
                return
            for item in resp.json().get("items", []):
                r = by_id.get(item.get("id"))
                if r is None:
                    continue
                stats = item.get("statistics") or {}
                content = item.get("contentDetails") or {}
                status = item.get("status") or {}
                r.views = _int(stats.get("viewCount"))
                r.likes = _int(stats.get("likeCount"))
                r.comments = _int(stats.get("commentCount"))
                r.duration_sec = _parse_duration(content.get("duration"))
                # 16:9 vs Shorts: search.list can't tell us, but a <= 60s
                # video on YouTube is a Short in practice.
                if r.duration_sec is not None and r.duration_sec <= 60:
                    r.width, r.height = 9, 16
                    r.content_tags = list(dict.fromkeys([*r.content_tags, "shorts"]))
                else:
                    r.width, r.height = 16, 9
                if status.get("license") == "creativeCommon":
                    r.rights_status = RIGHTS_CREATIVE_COMMONS
                    r.attribution = (
                        f'"{r.title}" by {r.creator_name or "unknown"} '
                        f"(CC BY 3.0) via YouTube -- {r.source_url}"
                    )


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


_QUOTA_MESSAGE = (
    "Hết quota YouTube API hôm nay (mặc định 10.000 đơn vị/ngày, mỗi lượt tìm tốn ~100). "
    "Quota reset lúc nửa đêm giờ Thái Bình Dương (khoảng 14-15h VN)."
)


def _error_reason(resp: "httpx.Response | None") -> str:
    """The Google API error `reason` (e.g. 'quotaExceeded') -- never the raw
    response text, which contains the API key in the request URL."""
    if resp is None:
        return ""
    try:
        return resp.json()["error"]["errors"][0].get("reason", "") or ""
    except (ValueError, KeyError, IndexError, TypeError):
        return ""
