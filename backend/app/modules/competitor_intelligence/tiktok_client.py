"""Thin httpx wrapper around TikTok's real, official v2 endpoints -- see
docs/features/76-competitor-content-analyzer.md's own API capability audit
for which products these are and why no "get any user's videos" call
exists here (it doesn't exist for a commercial app, period). Sibling to
app.modules.ai.image_client's own "wrap one external API behind a small,
stable surface" role, but httpx instead of a vendor SDK (TikTok has no
official Python SDK) -- httpx is already a project dependency
(requirements.txt), reused rather than adding `requests`.

Every call here has NOT been exercised against a real, approved TikTok
Developer app (this environment has no TikTok credentials) -- shapes below
match TikTok's own published v2 Login Kit / Display API documentation as
closely as this codebase can verify without live credentials. Flagged
here, in the setup doc, and in the PR description; verify against a real
sandbox app before depending on exact field names in production.
"""

import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.exceptions import ExternalServiceError

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
REVOKE_URL = "https://open.tiktokapis.com/v2/oauth/revoke/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
OEMBED_URL = "https://www.tiktok.com/oembed"

# The scopes this feature actually needs, per the capability audit -- own
# profile + own stats + own video list. Nothing here can ever return
# another user's data (see module docstring).
SCOPES = ("user.info.basic", "user.info.profile", "user.info.stats", "video.list")

USER_INFO_FIELDS = "open_id,union_id,avatar_url,display_name,username,follower_count,following_count,likes_count,video_count"
VIDEO_LIST_FIELDS = (
    "id,title,video_description,duration,cover_image_url,share_url,view_count,like_count,comment_count,share_count,create_time"
)

_TIMEOUT_SEC = 15.0


@dataclass(frozen=True)
class PKCEPair:
    code_verifier: str
    code_challenge: str


def generate_pkce_pair() -> PKCEPair:
    """RFC 7636 S256 -- TikTok's v2 authorize endpoint requires PKCE."""
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = hashlib.sha256(verifier.encode("ascii")).hexdigest()
    return PKCEPair(code_verifier=verifier, code_challenge=challenge)


def build_authorize_url(client_key: str, redirect_uri: str, state: str, code_challenge: str) -> str:
    params = {
        "client_key": client_key,
        "response_type": "code",
        "scope": ",".join(SCOPES),
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _post_form(url: str, data: dict) -> dict:
    try:
        response = httpx.post(
            url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=_TIMEOUT_SEC
        )
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"TikTok request failed: {exc}") from exc

    body = response.json() if response.content else {}
    if response.status_code >= 400 or "error" in body:
        error = body.get("error", {})
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise ExternalServiceError(f"TikTok API error ({response.status_code}): {message or body}")
    return body


def exchange_code_for_token(client_key: str, client_secret: str, code: str, redirect_uri: str, code_verifier: str) -> dict:
    return _post_form(
        TOKEN_URL,
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )


def refresh_access_token(client_key: str, client_secret: str, refresh_token: str) -> dict:
    return _post_form(
        TOKEN_URL,
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )


def revoke_token(client_key: str, client_secret: str, token: str) -> None:
    # Best-effort: a disconnect must always succeed locally even if TikTok's
    # revoke call fails (network error, already-expired token) -- the
    # caller (service.disconnect_account) deletes the local row regardless.
    try:
        _post_form(REVOKE_URL, {"client_key": client_key, "client_secret": client_secret, "token": token})
    except ExternalServiceError:
        pass


def _get_authorized(url: str, access_token: str, params: dict | None = None) -> dict:
    try:
        response = httpx.get(url, params=params, headers={"Authorization": f"Bearer {access_token}"}, timeout=_TIMEOUT_SEC)
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"TikTok request failed: {exc}") from exc

    body = response.json() if response.content else {}
    error = body.get("error") or {}
    if response.status_code >= 400 or (isinstance(error, dict) and error.get("code") not in (None, "ok")):
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise ExternalServiceError(f"TikTok API error ({response.status_code}): {message or body}")
    return body


def fetch_user_info(access_token: str) -> dict:
    body = _get_authorized(USER_INFO_URL, access_token, params={"fields": USER_INFO_FIELDS})
    return body.get("data", {}).get("user", {})


def fetch_video_list(access_token: str, cursor: int | None = None, max_count: int = 20) -> dict:
    """POST, not GET, per TikTok's own video.list spec (it's a paginated
    query with a body, not a simple resource fetch). Returns the raw
    `data` object: {"videos": [...], "cursor": int, "has_more": bool}.
    """
    payload = {"max_count": max_count}
    if cursor is not None:
        payload["cursor"] = cursor
    try:
        response = httpx.post(
            f"{VIDEO_LIST_URL}?fields={VIDEO_LIST_FIELDS}",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=_TIMEOUT_SEC,
        )
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"TikTok request failed: {exc}") from exc

    body = response.json() if response.content else {}
    error = body.get("error") or {}
    if response.status_code >= 400 or (isinstance(error, dict) and error.get("code") not in (None, "ok")):
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise ExternalServiceError(f"TikTok API error ({response.status_code}): {message or body}")
    return body.get("data", {"videos": [], "cursor": 0, "has_more": False})


def fetch_oembed(video_url: str) -> dict | None:
    """Public, unauthenticated, no app registration needed -- see module
    docstring. Returns None (never raises) on any failure: oEmbed
    enrichment is a nice-to-have when adding a CompetitorVideo, not a
    required step (the user's own manually-typed fields always work
    without it).
    """
    try:
        response = httpx.get(OEMBED_URL, params={"url": video_url}, timeout=_TIMEOUT_SEC)
        if response.status_code != 200:
            return None
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None
