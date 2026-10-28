"""Per-platform fetchers. Each returns {name, followers, total_views,
video_count} (None where the platform doesn't expose it) or raises
ExternalServiceError with a message safe to show the user.

YouTube uses the public channel statistics (API key, no OAuth); Facebook
uses the Graph API with a Page access token. Credentials go in headers,
never the query string: httpx logs full request URLs at INFO.
"""

import httpx

from app.core.exceptions import ExternalServiceError, ValidationError

_TIMEOUT = 20.0


def _get(url: str, params: dict, headers: dict) -> dict:
    host = httpx.URL(url).host
    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=_TIMEOUT)
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"Không kết nối được tới {host}: {exc.__class__.__name__}") from None
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        msg = err.get("message") if isinstance(err, dict) else None
        raise ExternalServiceError(f"{host} trả lỗi {resp.status_code}: {msg or resp.text[:200]}")
    return body


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_youtube(external_id: str, credential: str | None) -> dict:
    if not credential:
        raise ValidationError("Kênh YouTube chưa có YouTube Data API key.")
    body = _get(
        "https://www.googleapis.com/youtube/v3/channels",
        {"part": "snippet,statistics", "id": external_id},
        {"x-goog-api-key": credential},
    )
    items = body.get("items") or []
    if not items:
        raise ExternalServiceError(f"Không tìm thấy kênh YouTube có id {external_id!r}.")
    stats = items[0].get("statistics", {})
    hidden = stats.get("hiddenSubscriberCount")
    return {
        "name": items[0].get("snippet", {}).get("title"),
        "followers": None if hidden else _int(stats.get("subscriberCount")),
        "total_views": _int(stats.get("viewCount")),
        "video_count": _int(stats.get("videoCount")),
    }


def fetch_facebook(external_id: str, credential: str | None) -> dict:
    if not credential:
        raise ValidationError("Page Facebook chưa có access token.")
    body = _get(
        f"https://graph.facebook.com/v19.0/{external_id}",
        {"fields": "name,followers_count,fan_count"},
        {"Authorization": f"Bearer {credential}"},
    )
    return {
        "name": body.get("name"),
        "followers": _int(body.get("followers_count", body.get("fan_count"))),
        "total_views": None,
        "video_count": None,
    }


FETCHERS = {"youtube": fetch_youtube, "facebook": fetch_facebook}
