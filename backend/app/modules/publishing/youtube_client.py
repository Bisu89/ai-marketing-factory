"""Thin httpx wrapper around Google OAuth 2.0 + the YouTube Data API v3
upload endpoints. httpx only, no google-api-python-client -- same "wrap
one external API behind a small, stable surface with httpx, don't add a
vendor SDK" convention app.modules.competitor_intelligence.tiktok_client
already established.

Not exercised against a real approved Google OAuth project in this dev
environment (no credentials here) -- shapes match Google's published OAuth
2.0 + YouTube Data API v3 docs. Verify against a real project before
depending on exact error field names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.core.exceptions import ExternalServiceError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
VIDEOS_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMBNAIL_SET_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"

# youtube.upload is a "sensitive" scope (a consent-screen warning, an audit
# needed to go to production) -- youtube.readonly is added only to read
# back the connected channel's own title/thumbnail.
SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
)

# "22" = People & Blogs, the safest generic default. The user can change
# the category in YouTube Studio; a wrong-but-valid id never blocks upload.
DEFAULT_CATEGORY_ID = "22"

_TIMEOUT_SEC = 30.0
_UPLOAD_TIMEOUT_SEC = 900.0  # a 100-200 MB PUT over a home connection


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str | None
    expires_in: int


def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        # offline + consent so Google always returns a refresh_token, even
        # on a re-authorization of an already-granted channel.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _token_request(data: dict) -> TokenResponse:
    try:
        resp = httpx.post(TOKEN_URL, data=data, timeout=_TIMEOUT_SEC)
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"Google token request failed: {exc}") from exc
    body = resp.json() if resp.content else {}
    if resp.status_code >= 400 or "error" in body:
        raise ExternalServiceError(
            f"Google OAuth error ({resp.status_code}): {body.get('error_description') or body.get('error') or body}"
        )
    return TokenResponse(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_in=int(body.get("expires_in", 3600)),
    )


def exchange_code_for_token(client_id: str, client_secret: str, code: str, redirect_uri: str) -> TokenResponse:
    return _token_request({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> TokenResponse:
    return _token_request({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })


def revoke_token(token: str) -> None:
    try:
        httpx.post(REVOKE_URL, data={"token": token}, timeout=_TIMEOUT_SEC)
    except httpx.HTTPError:
        pass  # best-effort -- a local disconnect must still succeed


def fetch_my_channel(access_token: str) -> dict:
    """The authorizing user's own channel: {id, title, thumbnail_url}."""
    try:
        resp = httpx.get(
            CHANNELS_URL,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=_TIMEOUT_SEC,
        )
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"YouTube channels request failed: {exc}") from exc
    body = resp.json() if resp.content else {}
    if resp.status_code >= 400:
        raise ExternalServiceError(f"YouTube channels error ({resp.status_code}): {body.get('error', body)}")
    items = body.get("items") or []
    if not items:
        raise ExternalServiceError("This Google account has no YouTube channel.")
    snippet = items[0].get("snippet", {})
    thumbs = snippet.get("thumbnails", {})
    return {
        "id": items[0]["id"],
        "title": snippet.get("title", "YouTube channel"),
        "thumbnail_url": (thumbs.get("default") or {}).get("url"),
    }


def upload_video(
    access_token: str, video_path: Path, *, title: str, description: str, tags: list[str],
    privacy_status: str, category_id: str = DEFAULT_CATEGORY_ID,
) -> str:
    """Resumable upload in a single PUT (fine for the <~250 MB the Factory
    produces). Returns the new video id.
    """
    size = video_path.stat().st_size
    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": [t.lstrip("#") for t in tags][:15],
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }
    # 1. initiate the resumable session
    try:
        init = httpx.post(
            VIDEOS_UPLOAD_URL,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(size),
            },
            content=json.dumps(metadata),
            timeout=_TIMEOUT_SEC,
        )
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"YouTube upload init failed: {exc}") from exc
    if init.status_code >= 400:
        raise ExternalServiceError(f"YouTube upload init error ({init.status_code}): {init.text[:400]}")
    session_url = init.headers.get("location") or init.headers.get("Location")
    if not session_url:
        raise ExternalServiceError("YouTube did not return a resumable upload URL.")

    # 2. upload the bytes
    try:
        with video_path.open("rb") as fh:
            put = httpx.put(
                session_url,
                headers={"Content-Type": "video/*", "Content-Length": str(size)},
                content=fh.read(),
                timeout=_UPLOAD_TIMEOUT_SEC,
            )
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"YouTube video upload failed: {exc}") from exc
    body = put.json() if put.content else {}
    if put.status_code >= 400 or "id" not in body:
        raise ExternalServiceError(f"YouTube upload error ({put.status_code}): {body.get('error', put.text[:400])}")
    return body["id"]


def set_thumbnail(access_token: str, video_id: str, thumbnail_path: Path) -> None:
    """Best-effort -- a thumbnail failure never fails the upload (the video
    is already live; YouTube auto-picks a frame).
    """
    try:
        with thumbnail_path.open("rb") as fh:
            resp = httpx.post(
                THUMBNAIL_SET_URL,
                params={"videoId": video_id},
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "image/jpeg"},
                content=fh.read(),
                timeout=_TIMEOUT_SEC,
            )
        if resp.status_code >= 400:
            raise ExternalServiceError(f"thumbnail set failed ({resp.status_code}): {resp.text[:200]}")
    except (httpx.HTTPError, OSError) as exc:
        raise ExternalServiceError(f"thumbnail set failed: {exc}") from exc
