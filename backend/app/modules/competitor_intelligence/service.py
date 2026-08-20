"""Core module logic: OAuth state bookkeeping, TikTokAccountLink/TikTokVideo
persistence, CompetitorVideo CRUD, and the pure prompt-build/response-parse
functions for pattern analysis (the actual AI call happens in the
composition root -- see app/api/v1/endpoints/competitor_analysis.py --
same "module builds the prompt, composition root calls call_structured()"
split content_generate.py/beat_generate.py already use elsewhere in this
codebase, since app.modules.ai.llm_client must never be imported directly
by a module's own service.py).
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.modules.competitor_intelligence import tiktok_client
from app.modules.competitor_intelligence.models import COMPETITOR_ANALYSIS_FIELDS, CompetitorVideo, TikTokAccountLink, TikTokVideo

# -- OAuth state (PKCE code_verifier keyed by `state`) -----------------------
#
# In-memory, not a DB table: the authorize -> callback round trip happens
# within one interactive browser session (seconds to a couple of minutes),
# and this app is single-user/desktop-local -- same tradeoff
# app.modules.asset.import_service's own _CANCEL_EVENTS dict already makes
# for short-lived, process-local coordination state. Swept for entries
# older than _STATE_TTL_SEC on every access so a never-completed flow
# can't leak memory across a long-running process.

_STATE_TTL_SEC = 600
_oauth_state_lock = threading.Lock()
_oauth_state: dict[str, tuple[str, float]] = {}  # state -> (code_verifier, created_at)


def start_oauth_state(code_verifier: str) -> str:
    import secrets

    state = secrets.token_urlsafe(24)
    now = time.monotonic()
    with _oauth_state_lock:
        stale = [s for s, (_, created) in _oauth_state.items() if now - created > _STATE_TTL_SEC]
        for s in stale:
            del _oauth_state[s]
        _oauth_state[state] = (code_verifier, now)
    return state


def pop_oauth_state(state: str) -> str | None:
    with _oauth_state_lock:
        entry = _oauth_state.pop(state, None)
    if entry is None:
        return None
    code_verifier, created = entry
    if time.monotonic() - created > _STATE_TTL_SEC:
        return None
    return code_verifier


# -- TikTokAccountLink ---------------------------------------------------


def get_active_account(db: Session) -> TikTokAccountLink | None:
    return db.query(TikTokAccountLink).filter(TikTokAccountLink.status == "connected").order_by(TikTokAccountLink.connected_at.desc()).first()


def upsert_account_from_token(db: Session, token_resp: dict, profile: dict) -> TikTokAccountLink:
    open_id = token_resp.get("open_id") or profile.get("open_id")
    if not open_id:
        raise ExternalServiceError("TikTok token response is missing open_id.")

    now = datetime.now(timezone.utc)
    expires_in = token_resp.get("expires_in", 0)
    refresh_expires_in = token_resp.get("refresh_expires_in", 0)

    account = db.query(TikTokAccountLink).filter(TikTokAccountLink.open_id == open_id).first()
    if account is None:
        account = TikTokAccountLink(open_id=open_id)
        db.add(account)

    account.username = profile.get("username")
    account.display_name = profile.get("display_name")
    account.avatar_url = profile.get("avatar_url")
    account.follower_count = profile.get("follower_count")
    account.following_count = profile.get("following_count")
    account.likes_count = profile.get("likes_count")
    account.video_count = profile.get("video_count")

    account.access_token = token_resp["access_token"]
    account.refresh_token = token_resp["refresh_token"]
    account.access_token_expires_at = now + timedelta(seconds=expires_in)
    account.refresh_token_expires_at = now + timedelta(seconds=refresh_expires_in)
    account.scope = token_resp.get("scope", "")
    account.status = "connected"

    db.commit()
    db.refresh(account)
    return account


# Refresh proactively once within this margin of real expiry -- avoids a
# request failing mid-call with a just-expired token.
_REFRESH_MARGIN_SEC = 300


def get_valid_access_token(db: Session, account: TikTokAccountLink, client_key: str, client_secret: str) -> str:
    now = datetime.now(timezone.utc)
    if account.access_token_expires_at - timedelta(seconds=_REFRESH_MARGIN_SEC) > now:
        return account.access_token

    if account.refresh_token_expires_at <= now:
        account.status = "token_expired"
        db.commit()
        raise ExternalServiceError("TikTok refresh token has expired -- reconnect the account in Settings.")

    token_resp = tiktok_client.refresh_access_token(client_key, client_secret, account.refresh_token)
    expires_in = token_resp.get("expires_in", 0)
    refresh_expires_in = token_resp.get("refresh_expires_in", 0)
    account.access_token = token_resp["access_token"]
    account.refresh_token = token_resp.get("refresh_token", account.refresh_token)
    account.access_token_expires_at = now + timedelta(seconds=expires_in)
    if refresh_expires_in:
        account.refresh_token_expires_at = now + timedelta(seconds=refresh_expires_in)
    db.commit()
    db.refresh(account)
    return account.access_token


def disconnect_account(db: Session, account: TikTokAccountLink, client_key: str, client_secret: str) -> None:
    tiktok_client.revoke_token(client_key, client_secret, account.access_token)
    db.delete(account)
    db.commit()


# -- TikTokVideo ----------------------------------------------------------


def upsert_videos(db: Session, account_link_id: int, videos: list[dict]) -> int:
    count = 0
    for v in videos:
        row = (
            db.query(TikTokVideo)
            .filter(TikTokVideo.account_link_id == account_link_id, TikTokVideo.tiktok_video_id == v["id"])
            .first()
        )
        if row is None:
            row = TikTokVideo(account_link_id=account_link_id, tiktok_video_id=v["id"])
            db.add(row)

        row.title = v.get("title")
        row.video_description = v.get("video_description")
        row.duration_sec = v.get("duration")
        row.cover_image_url = v.get("cover_image_url")
        row.share_url = v.get("share_url")
        row.view_count = v.get("view_count")
        row.like_count = v.get("like_count")
        row.comment_count = v.get("comment_count")
        row.share_count = v.get("share_count")
        create_time = v.get("create_time")
        row.posted_at = datetime.fromtimestamp(create_time, tz=timezone.utc) if create_time else None
        row.synced_at = datetime.now(timezone.utc)
        count += 1
    db.commit()
    return count


def list_videos(db: Session, account_link_id: int) -> list[TikTokVideo]:
    return db.query(TikTokVideo).filter(TikTokVideo.account_link_id == account_link_id).order_by(TikTokVideo.posted_at.desc()).all()


# -- CompetitorVideo --------------------------------------------------------


def create_competitor_video(
    db: Session,
    source_url: str,
    competitor_handle: str | None,
    title_caption: str | None,
    duration_sec: float | None,
    notes: str | None,
) -> CompetitorVideo:
    if not source_url.strip():
        raise ValidationError("source_url khong duoc de trong.")

    video = CompetitorVideo(
        source_url=source_url.strip(),
        competitor_handle=(competitor_handle or "").strip() or None,
        title_caption=(title_caption or "").strip() or None,
        duration_sec=duration_sec,
        notes=(notes or "").strip() or None,
    )

    # Best-effort enrichment -- never blocks/fails the create if oEmbed is
    # unreachable or the URL isn't a real TikTok video (see tiktok_client.
    # fetch_oembed's own "never raises" contract). Only fills gaps the user
    # didn't already type in themselves.
    oembed = tiktok_client.fetch_oembed(video.source_url)
    if oembed:
        video.thumbnail_url = video.thumbnail_url or oembed.get("thumbnail_url")
        video.author_name = video.author_name or oembed.get("author_name")
        if not video.title_caption:
            video.title_caption = oembed.get("title")

    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def list_competitor_videos(db: Session) -> list[CompetitorVideo]:
    return db.query(CompetitorVideo).order_by(CompetitorVideo.added_at.desc()).all()


def get_competitor_video(db: Session, video_id: int) -> CompetitorVideo:
    video = db.get(CompetitorVideo, video_id)
    if video is None:
        raise NotFoundError("CompetitorVideo", video_id)
    return video


def delete_competitor_video(db: Session, video: CompetitorVideo) -> None:
    db.delete(video)
    db.commit()


# -- Pattern analysis: prompt build + response parse (pure) -----------------

ANALYSIS_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "emotional_pattern": {"type": "string"},
            "hook_structure": {"type": "string"},
            "conflict_type": {"type": "string"},
            "character_type": {"type": "string"},
            "ending_style": {"type": "string"},
            "estimated_format": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        "required": list(COMPETITOR_ANALYSIS_FIELDS) + ["reasoning"],
        "additionalProperties": False,
    },
}

_ANALYSIS_SYSTEM_PROMPT = (
    "Ban la mot chuyen gia phan tich content ngan (TikTok/Reels/Shorts). "
    "Nhiem vu cua ban la trich xuat CAC MAU HINH TRUU TUONG (abstract patterns) tu mo ta cong khai "
    "cua mot video doi thu, TUYET DOI KHONG duoc sao chep, dien giai lai, hay tao ra bat ky doan "
    "script/loi thoai cu the nao tu video do. Chi mo ta cau truc/khuon mau o muc khai quat "
    "(vi du: 'phan bat ngo o giua video', khong phai 'nhan vat A noi cau X')."
)


def build_analysis_prompt(video: CompetitorVideo) -> tuple[str, str]:
    if not video.title_caption and not video.notes:
        raise ValidationError(
            "CompetitorVideo chua co title_caption/notes -- can it nhat mo ta cong khai nguoi dung tu doc "
            "va nhap vao truoc khi phan tich."
        )
    parts = [f"URL: {video.source_url}"]
    if video.competitor_handle:
        parts.append(f"Kenh doi thu: {video.competitor_handle}")
    if video.title_caption:
        parts.append(f"Tieu de/caption cong khai: {video.title_caption}")
    if video.duration_sec:
        parts.append(f"Thoi luong: {video.duration_sec:.0f} giay")
    if video.notes:
        parts.append(f"Mo ta them nguoi dung ghi lai (nhung gi ho xem duoc cong khai): {video.notes}")
    parts.append(
        "\nTra ve JSON voi cac truong: emotional_pattern, hook_structure, conflict_type, "
        "character_type, ending_style, estimated_format, reasoning (1-2 cau giai thich ngan gon)."
    )
    return _ANALYSIS_SYSTEM_PROMPT, "\n".join(parts)


def parse_analysis_response(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExternalServiceError(f"AI tra ve JSON khong hop le: {exc}") from exc

    missing = [f for f in (*COMPETITOR_ANALYSIS_FIELDS, "reasoning") if not data.get(f)]
    if missing:
        raise ExternalServiceError(f"AI response thieu truong: {missing}")
    return data


def persist_analysis(db: Session, video: CompetitorVideo, parsed: dict, provider: str, model: str, input_tokens: int | None, output_tokens: int | None) -> CompetitorVideo:
    for field in COMPETITOR_ANALYSIS_FIELDS:
        setattr(video, field, parsed[field])
    video.reasoning = parsed["reasoning"]
    video.analyzed_at = datetime.now(timezone.utc)
    video.analysis_provider = provider
    video.analysis_model = model
    video.analysis_input_tokens = input_tokens
    video.analysis_output_tokens = output_tokens
    db.commit()
    db.refresh(video)
    return video
