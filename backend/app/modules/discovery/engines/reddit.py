"""Reddit search engine.

Uses Reddit's public search JSON (`/search.json`) -- optionally
authenticated with the user's own installed-app OAuth credentials
(APP_REDDIT_CLIENT_ID / APP_REDDIT_CLIENT_SECRET) for a higher rate limit.
No credentials -> anonymous requests with a descriptive User-Agent, which
is enough for a single-user desktop app.

Reddit content is NOT reusable by default -- every result is
rightsStatus = UNKNOWN (brief section 3). We never assume otherwise.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.modules.discovery.contracts import (
    PLATFORM_REDDIT,
    RIGHTS_UNKNOWN,
    EngineOutcome,
    VideoResult,
)
from app.modules.discovery.engines.base import BaseEngine, SearchOptions

logger = logging.getLogger(__name__)

_USER_AGENT = "AIContentLibrary/1.0 (Viral Source Radar; desktop app)"
_SEARCH_URL = "https://www.reddit.com/search.json"
_OAUTH_SEARCH_URL = "https://oauth.reddit.com/search"
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"

# Visual-content signals -- a post with none of these is unlikely to be a
# usable short-form source, so we skip it (brief section 3: "prioritize
# visual content").
_VIDEO_HINTS = ("hosted:video", "rich:video", "link")


class RedditEngine(BaseEngine):
    platform = PLATFORM_REDDIT

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client
        self._token: tuple[str, float] | None = None

    def is_configured(self) -> bool:
        # Anonymous search works; the engine is always "available".
        return True

    def unavailable_reason(self) -> str:  # pragma: no cover
        return "Reddit search is unavailable"

    # -- auth ---------------------------------------------------------
    def _bearer_token(self, client: httpx.Client) -> str | None:
        s = get_settings()
        cid = getattr(s, "reddit_client_id", None)
        secret = getattr(s, "reddit_client_secret", None)
        if not cid or not secret:
            return None
        if self._token and self._token[1] > time.time() + 30:
            return self._token[0]
        try:
            resp = client.post(
                _TOKEN_URL,
                auth=(cid, secret),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": _USER_AGENT},
                timeout=15,
            )
            resp.raise_for_status()
            body = resp.json()
            token = body["access_token"]
            self._token = (token, time.time() + int(body.get("expires_in", 3600)))
            return token
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("reddit: token fetch failed, falling back to anonymous: %s", exc)
            return None

    # -- search -----------------------------------------------------
    def search(self, query: str, options: SearchOptions) -> EngineOutcome:
        client = self._client or httpx.Client(follow_redirects=True)
        owns_client = self._client is None
        try:
            queries = options.queries or [query]
            collected: dict[str, VideoResult] = {}
            token = self._bearer_token(client)
            forbidden = False
            other_error: str | None = None
            for q in queries:
                try:
                    for r in self._search_one(client, q, options, token):
                        collected.setdefault(r.source_url, r)
                except httpx.HTTPStatusError as exc:
                    if exc.response is not None and exc.response.status_code in (401, 403, 429):
                        forbidden = True
                    else:
                        other_error = str(exc)
                    logger.warning("reddit: query %r failed: %s", q, exc)
                    continue
                except httpx.HTTPError as exc:
                    other_error = str(exc)
                    logger.warning("reddit: query %r failed: %s", q, exc)
                    continue
            if collected:
                return EngineOutcome.ok(self.platform, list(collected.values()))
            # Nothing collected -- distinguish "genuinely no matches" from
            # "Reddit blocked us". Anonymous search is 403'd for most
            # non-browser clients now, so a 403 without credentials means
            # the user needs to add a Reddit app id/secret in Settings.
            if forbidden and not token:
                return EngineOutcome.unavailable(
                    self.platform,
                    "Reddit chặn tìm kiếm ẩn danh. Thêm Reddit API client id/secret "
                    "trong Settings (tạo app loại 'script' tại reddit.com/prefs/apps).",
                )
            if forbidden:
                return EngineOutcome.failed(
                    self.platform, "Reddit từ chối truy cập (kiểm tra lại client id/secret)."
                )
            if other_error:
                return EngineOutcome.failed(self.platform, f"Reddit request failed: {other_error}")
            return EngineOutcome.ok(self.platform, [])
        except httpx.HTTPError as exc:
            logger.exception("reddit: search failed")
            return EngineOutcome.failed(self.platform, f"Reddit request failed: {exc}")
        finally:
            if owns_client:
                client.close()

    def _search_one(
        self, client: httpx.Client, q: str, options: SearchOptions, token: str | None
    ) -> list[VideoResult]:
        params = {
            "q": q,
            "sort": "top",
            "t": "year" if (options.max_age_days or 366) > 90 else "month",
            "limit": str(min(max(options.limit_per_query, 25), 100)),
            "type": "link",
            "raw_json": "1",
        }
        headers = {"User-Agent": _USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            url = _OAUTH_SEARCH_URL
        else:
            url = _SEARCH_URL
        resp = client.get(url, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        children = resp.json().get("data", {}).get("children", [])
        out: list[VideoResult] = []
        for child in children:
            data = child.get("data") or {}
            result = _post_to_result(data)
            if result is not None:
                out.append(result)
        return out


def _post_to_result(data: dict) -> VideoResult | None:
    if data.get("over_18"):
        return None
    hint = data.get("post_hint") or ""
    is_video = bool(data.get("is_video")) or hint in _VIDEO_HINTS or "v.redd.it" in (data.get("url") or "")
    if not is_video and hint not in ("image", "rich:video", "link"):
        return None

    permalink = data.get("permalink") or ""
    source_url = f"https://www.reddit.com{permalink}" if permalink else (data.get("url") or "")
    if not source_url:
        return None

    created = data.get("created_utc")
    published = (
        datetime.fromtimestamp(created, tz=timezone.utc) if isinstance(created, (int, float)) else None
    )

    media = data.get("media") or {}
    reddit_video = media.get("reddit_video") or {}
    duration = reddit_video.get("duration")
    width = reddit_video.get("width") or None
    height = reddit_video.get("height") or None

    thumb = data.get("thumbnail")
    if thumb in ("self", "default", "nsfw", "spoiler", "", None):
        thumb = None
    preview = (data.get("preview") or {}).get("images") or []
    if not thumb and preview:
        thumb = (preview[0].get("source") or {}).get("url")

    subreddit = data.get("subreddit")
    author = data.get("author")

    return VideoResult(
        platform=PLATFORM_REDDIT,
        id=str(data.get("id") or ""),
        source_url=source_url,
        title=data.get("title") or "Untitled",
        description=(data.get("selftext") or None),
        thumbnail_url=thumb,
        creator_name=(f"u/{author}" if author and author != "[deleted]" else None),
        creator_url=(f"https://www.reddit.com/user/{author}" if author and author != "[deleted]" else None),
        published_at=published,
        duration_sec=int(duration) if isinstance(duration, (int, float)) else None,
        views=None,  # Reddit does not expose view counts
        likes=int(data["score"]) if isinstance(data.get("score"), int) else None,
        comments=int(data["num_comments"]) if isinstance(data.get("num_comments"), int) else None,
        shares=None,
        width=int(width) if width else None,
        height=int(height) if height else None,
        content_tags=[f"r/{subreddit}"] if subreddit else [],
        rights_status=RIGHTS_UNKNOWN,
    )
