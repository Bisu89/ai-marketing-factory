"""Database-backed persistence + OAuth-state + token-refresh for the
Publishing module. "SessionLocal per call" shape (same as
app.modules.news.service / app.modules.batch.service) -- callable from both
request handlers and the background upload thread.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import SessionLocal
from app.modules.publishing import youtube_client
from app.modules.publishing.models import YouTubeChannel, YouTubeUploadJob

logger = logging.getLogger(__name__)

# state -> created_at (monotonic). CSRF/replay guard for the OAuth round
# trip -- same in-memory + lock + TTL shape as
# app.modules.competitor_intelligence.service's own oauth state.
_oauth_state: dict[str, float] = {}
_oauth_state_lock = threading.Lock()
_OAUTH_STATE_TTL_SEC = 600
# Refresh the access token when it has under this long left.
_TOKEN_REFRESH_MARGIN_SEC = 120


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def start_oauth_state() -> str:
    state = secrets.token_urlsafe(24)
    now = time.monotonic()
    with _oauth_state_lock:
        for key, created in list(_oauth_state.items()):
            if now - created > _OAUTH_STATE_TTL_SEC:
                del _oauth_state[key]
        _oauth_state[state] = now
    return state


def consume_oauth_state(state: str) -> bool:
    with _oauth_state_lock:
        created = _oauth_state.pop(state, None)
    return created is not None and (time.monotonic() - created) <= _OAUTH_STATE_TTL_SEC


def _require_oauth_config(settings: Settings) -> tuple[str, str]:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise ValidationError(
            "Google OAuth is not configured. Add your Google Cloud OAuth client ID and secret in Settings."
        )
    return settings.google_oauth_client_id, settings.google_oauth_client_secret


# -- OAuth connect ----------------------------------------------------


def build_authorize_url(settings: Settings) -> str:
    client_id, _ = _require_oauth_config(settings)
    return youtube_client.build_authorize_url(client_id, settings.youtube_redirect_uri, start_oauth_state())


def connect_channel_from_code(settings: Settings, code: str) -> YouTubeChannel:
    client_id, client_secret = _require_oauth_config(settings)
    token = youtube_client.exchange_code_for_token(client_id, client_secret, code, settings.youtube_redirect_uri)
    if not token.refresh_token:
        raise ValidationError(
            "Google did not return a refresh token. Remove this app's access at "
            "myaccount.google.com/permissions and connect again."
        )
    info = youtube_client.fetch_my_channel(token.access_token)
    expires_at = _utcnow() + timedelta(seconds=token.expires_in)

    db = SessionLocal()
    try:
        channel = db.query(YouTubeChannel).filter(YouTubeChannel.channel_id == info["id"]).first()
        if channel is None:
            channel = YouTubeChannel(channel_id=info["id"])
            db.add(channel)
        channel.title = info["title"]
        channel.thumbnail_url = info["thumbnail_url"]
        channel.refresh_token = token.refresh_token
        channel.access_token = token.access_token
        channel.access_token_expires_at = expires_at
        channel.enabled = True
        channel.last_error = None
        db.commit()
        db.refresh(channel)
        db.expunge(channel)
        return channel
    finally:
        db.close()


# -- Channel CRUD ---------------------------------------------------


def list_channels() -> list[YouTubeChannel]:
    db = SessionLocal()
    try:
        channels = db.query(YouTubeChannel).order_by(YouTubeChannel.title).all()
        db.expunge_all()
        return channels
    finally:
        db.close()


def completed_upload_counts() -> dict[int, int]:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(YouTubeUploadJob.channel_pk, func.count(YouTubeUploadJob.id))
            .where(YouTubeUploadJob.status == "completed")
            .group_by(YouTubeUploadJob.channel_pk)
        ).all()
        return {pk: n for pk, n in rows}
    finally:
        db.close()


def get_channel(channel_pk: int) -> YouTubeChannel:
    db = SessionLocal()
    try:
        channel = db.get(YouTubeChannel, channel_pk)
        if channel is None:
            raise NotFoundError("YouTube channel", channel_pk)
        db.expunge(channel)
        return channel
    finally:
        db.close()


def update_channel(channel_pk: int, **fields) -> YouTubeChannel:
    db = SessionLocal()
    try:
        channel = db.get(YouTubeChannel, channel_pk)
        if channel is None:
            raise NotFoundError("YouTube channel", channel_pk)
        for key, value in fields.items():
            if value is not None:
                setattr(channel, key, value)
        db.commit()
        db.refresh(channel)
        db.expunge(channel)
        return channel
    finally:
        db.close()


def disconnect_channel(channel_pk: int) -> None:
    db = SessionLocal()
    try:
        channel = db.get(YouTubeChannel, channel_pk)
        if channel is None:
            raise NotFoundError("YouTube channel", channel_pk)
        token = channel.refresh_token
        db.delete(channel)
        db.commit()
    finally:
        db.close()
    if token:
        youtube_client.revoke_token(token)


def get_fresh_access_token(channel_pk: int, settings: Settings) -> str:
    """Returns a valid access token, refreshing (and persisting) it if it
    is missing or within the refresh margin of expiry.
    """
    client_id, client_secret = _require_oauth_config(settings)
    db = SessionLocal()
    try:
        channel = db.get(YouTubeChannel, channel_pk)
        if channel is None:
            raise NotFoundError("YouTube channel", channel_pk)
        exp = channel.access_token_expires_at
        if exp is not None and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        still_valid = channel.access_token and exp and exp - _utcnow() > timedelta(seconds=_TOKEN_REFRESH_MARGIN_SEC)
        if still_valid:
            return channel.access_token

        try:
            token = youtube_client.refresh_access_token(client_id, client_secret, channel.refresh_token)
        except Exception as exc:  # noqa: BLE001
            channel.last_error = f"Token refresh failed: {exc}"
            db.commit()
            raise
        channel.access_token = token.access_token
        channel.access_token_expires_at = _utcnow() + timedelta(seconds=token.expires_in)
        if token.refresh_token:
            channel.refresh_token = token.refresh_token
        channel.last_error = None
        db.commit()
        return token.access_token
    finally:
        db.close()


# -- Upload jobs --------------------------------------------------


def list_uploads(limit: int = 100) -> list[YouTubeUploadJob]:
    db = SessionLocal()
    try:
        jobs = (
            db.query(YouTubeUploadJob)
            .options(selectinload(YouTubeUploadJob.channel))
            .order_by(YouTubeUploadJob.id.desc())
            .limit(limit)
            .all()
        )
        db.expunge_all()
        return jobs
    finally:
        db.close()


def get_upload(job_id: int) -> YouTubeUploadJob:
    db = SessionLocal()
    try:
        job = (
            db.query(YouTubeUploadJob)
            .options(selectinload(YouTubeUploadJob.channel))
            .filter(YouTubeUploadJob.id == job_id)
            .first()
        )
        if job is None:
            raise NotFoundError("Upload job", job_id)
        db.expunge_all()
        return job
    finally:
        db.close()


def existing_upload(channel_pk: int, project_id: int) -> YouTubeUploadJob | None:
    db = SessionLocal()
    try:
        job = (
            db.query(YouTubeUploadJob)
            .filter(
                YouTubeUploadJob.channel_pk == channel_pk,
                YouTubeUploadJob.project_id == project_id,
                YouTubeUploadJob.status.in_(("pending", "uploading", "completed")),
            )
            .order_by(YouTubeUploadJob.id.desc())
            .first()
        )
        if job is not None:
            db.expunge(job)
        return job
    finally:
        db.close()


def create_upload_job(
    *, channel_pk: int, project_id: int, render_job_id: int | None, privacy: str,
    title: str, description: str, video_path: str,
) -> int:
    db = SessionLocal()
    try:
        job = YouTubeUploadJob(
            channel_pk=channel_pk, project_id=project_id, render_job_id=render_job_id,
            requested_privacy=privacy, title=title, description=description, video_path=video_path,
            status="pending",
        )
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


def set_upload_fields(job_id: int, **fields) -> None:
    db = SessionLocal()
    try:
        job = db.get(YouTubeUploadJob, job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        if fields.get("status") in ("completed", "failed"):
            job.completed_at = _utcnow()
        db.commit()
    finally:
        db.close()


def reconcile_uploads_on_startup() -> None:
    """Any upload left 'uploading' by a previous process is marked
    'interrupted' -- the same crash-recovery shape as
    reconcile_factory_runs_on_startup. Never auto-retried (a video may or
    may not have actually landed on YouTube); the user retries explicitly.
    """
    db = SessionLocal()
    try:
        stuck = db.query(YouTubeUploadJob).filter(YouTubeUploadJob.status.in_(("pending", "uploading"))).all()
        for job in stuck:
            job.status = "interrupted"
            job.error_message = "The app restarted while this upload was in progress."
            job.completed_at = _utcnow()
        if stuck:
            db.commit()
            logger.info("Marked %d interrupted YouTube upload(s) on startup", len(stuck))
    finally:
        db.close()
