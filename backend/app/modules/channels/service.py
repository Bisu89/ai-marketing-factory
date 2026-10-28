"""Owned-channel persistence + the sync operation. SessionLocal per call,
detached rows -- same shape as app.modules.story.service.
"""

import threading
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import LibraryError, NotFoundError, ValidationError
from app.db.session import SessionLocal
from app.modules.channels.adapters import FETCHERS
from app.modules.channels.models import ChannelMetricDaily, OwnedChannel, SyncRun

# One sync per channel at a time (double-click / background loop overlap).
_sync_lock = threading.Lock()
_syncing: set[int] = set()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_channel(**fields) -> OwnedChannel:
    db = SessionLocal()
    try:
        row = OwnedChannel(**fields)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValidationError("Kênh này đã được thêm rồi.") from None
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_channels() -> list[OwnedChannel]:
    db = SessionLocal()
    try:
        rows = db.query(OwnedChannel).order_by(OwnedChannel.id).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def get_channel(channel_id: int) -> OwnedChannel:
    db = SessionLocal()
    try:
        row = db.get(OwnedChannel, channel_id)
        if row is None:
            raise NotFoundError("Channel", channel_id)
        db.expunge(row)
        return row
    finally:
        db.close()


def update_channel(channel_id: int, **fields) -> OwnedChannel:
    db = SessionLocal()
    try:
        row = db.get(OwnedChannel, channel_id)
        if row is None:
            raise NotFoundError("Channel", channel_id)
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def delete_channel(channel_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(OwnedChannel, channel_id)
        if row is None:
            raise NotFoundError("Channel", channel_id)
        db.query(ChannelMetricDaily).filter_by(channel_id=channel_id).delete()
        db.query(SyncRun).filter_by(channel_id=channel_id).delete()
        db.delete(row)
        db.commit()
    finally:
        db.close()


def list_metrics(channel_id: int, limit: int = 90) -> list[ChannelMetricDaily]:
    get_channel(channel_id)
    db = SessionLocal()
    try:
        rows = (
            db.query(ChannelMetricDaily)
            .filter_by(channel_id=channel_id)
            .order_by(ChannelMetricDaily.day.desc())
            .limit(limit)
            .all()
        )
        db.expunge_all()
        return list(reversed(rows))
    finally:
        db.close()


def list_sync_runs(channel_id: int, limit: int = 20) -> list[SyncRun]:
    get_channel(channel_id)
    db = SessionLocal()
    try:
        rows = db.query(SyncRun).filter_by(channel_id=channel_id).order_by(SyncRun.id.desc()).limit(limit).all()
        db.expunge_all()
        return rows
    finally:
        db.close()


def sync_channel(channel_id: int) -> SyncRun:
    """Fetch the channel's current numbers and upsert today's metric row.
    Always records a SyncRun and the channel's last-sync fields, success or
    failure; a failure is returned (status 'error'), not raised, so the UI
    can show the reason on the card.
    """
    channel = get_channel(channel_id)
    fetch = FETCHERS.get(channel.platform)
    if fetch is None:
        raise ValidationError(f"Chưa hỗ trợ nền tảng {channel.platform!r}.")

    with _sync_lock:
        if channel_id in _syncing:
            raise ValidationError("Kênh này đang được đồng bộ.")
        _syncing.add(channel_id)
    try:
        db = SessionLocal()
        try:
            run = SyncRun(channel_id=channel_id)
            db.add(run)
            db.commit()
            db.refresh(run)

            try:
                data = fetch(channel.external_id, channel.credential)
                status, message = "ok", None
            except LibraryError as exc:
                data, status, message = None, "error", str(exc)

            now = _utcnow()
            row = db.get(OwnedChannel, channel_id)
            if data is not None:
                today = now.date()
                metric = db.query(ChannelMetricDaily).filter_by(channel_id=channel_id, day=today).one_or_none()
                if metric is None:
                    metric = ChannelMetricDaily(channel_id=channel_id, day=today)
                    db.add(metric)
                metric.followers = data["followers"]
                metric.total_views = data["total_views"]
                metric.video_count = data["video_count"]
                if data.get("name") and row is not None:
                    row.name = data["name"]
            run.status, run.message, run.finished_at = status, message, now
            if row is not None:
                row.last_synced_at, row.last_sync_status, row.last_sync_message = now, status, message
            db.commit()
            db.refresh(run)
            db.expunge(run)
            return run
        finally:
            db.close()
    finally:
        with _sync_lock:
            _syncing.discard(channel_id)
