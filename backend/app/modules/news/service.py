"""Database-backed persistence + fetch orchestration for NewsSource/NewsItem.

"SessionLocal per call" shape (same as app.modules.batch.service /
app.modules.beat.project_service) -- called from both request handlers and
the background poll thread (app/main.py's news-poll loop), so it can never
depend on a request-scoped session.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import SessionLocal
from app.modules.news.feeds import FeedFetchError, FetchedEntry, fetch_feed
from app.modules.news.models import NEWS_ITEM_ACTIVE_STATUSES, NewsItem, NewsSource
from app.modules.news.schemas import FetchResult

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# -- NewsSource CRUD ---------------------------------------------------


def list_sources() -> list[NewsSource]:
    db = SessionLocal()
    try:
        sources = db.query(NewsSource).order_by(NewsSource.name).all()
        db.expunge_all()
        return sources
    finally:
        db.close()


def pending_counts_by_source() -> dict[int, int]:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(NewsItem.source_id, func.count(NewsItem.id))
            .where(NewsItem.status.in_(NEWS_ITEM_ACTIVE_STATUSES))
            .group_by(NewsItem.source_id)
        ).all()
        return {source_id: count for source_id, count in rows}
    finally:
        db.close()


def get_source(source_id: int) -> NewsSource:
    db = SessionLocal()
    try:
        source = db.get(NewsSource, source_id)
        if source is None:
            raise NotFoundError("News source", source_id)
        db.expunge(source)
        return source
    finally:
        db.close()


def create_source(*, name: str, feed_url: str, category: str | None, language: str, enabled: bool) -> NewsSource:
    db = SessionLocal()
    try:
        existing = db.query(NewsSource).filter(NewsSource.feed_url == feed_url).first()
        if existing is not None:
            raise ValidationError(f"A source with this feed URL already exists: {existing.name}")
        source = NewsSource(
            name=name, feed_url=feed_url, category=category, language=language, enabled=enabled
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        db.expunge(source)
        return source
    finally:
        db.close()


def update_source(source_id: int, **fields) -> NewsSource:
    db = SessionLocal()
    try:
        source = db.get(NewsSource, source_id)
        if source is None:
            raise NotFoundError("News source", source_id)
        for key, value in fields.items():
            if value is not None:
                setattr(source, key, value)
        db.commit()
        db.refresh(source)
        db.expunge(source)
        return source
    finally:
        db.close()


def delete_source(source_id: int) -> None:
    db = SessionLocal()
    try:
        source = db.get(NewsSource, source_id)
        if source is None:
            raise NotFoundError("News source", source_id)
        db.delete(source)
        db.commit()
    finally:
        db.close()


# -- NewsItem queries -------------------------------------------------


def list_items(
    *,
    status: str | None = None,
    source_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[NewsItem], int]:
    db = SessionLocal()
    try:
        query = db.query(NewsItem).options(selectinload(NewsItem.source))
        if status is not None:
            query = query.filter(NewsItem.status == status)
        if source_id is not None:
            query = query.filter(NewsItem.source_id == source_id)
        total = query.count()
        items = (
            query.order_by(NewsItem.published_at.desc().nullslast(), NewsItem.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        db.expunge_all()
        return items, total
    finally:
        db.close()


def get_item(item_id: int) -> NewsItem:
    db = SessionLocal()
    try:
        item = db.query(NewsItem).options(selectinload(NewsItem.source)).filter(NewsItem.id == item_id).first()
        if item is None:
            raise NotFoundError("News item", item_id)
        db.expunge_all()
        return item
    finally:
        db.close()


def get_items(item_ids: list[int]) -> list[NewsItem]:
    db = SessionLocal()
    try:
        items = (
            db.query(NewsItem)
            .options(selectinload(NewsItem.source))
            .filter(NewsItem.id.in_(item_ids))
            .all()
        )
        db.expunge_all()
        return items
    finally:
        db.close()


def update_item(item_id: int, **fields) -> NewsItem:
    db = SessionLocal()
    try:
        item = db.get(NewsItem, item_id)
        if item is None:
            raise NotFoundError("News item", item_id)
        for key, value in fields.items():
            if value is not None:
                setattr(item, key, value)
        db.commit()
        db.refresh(item)
        db.expunge(item)
        return item
    finally:
        db.close()


def set_item_fields(item_id: int, **fields) -> None:
    db = SessionLocal()
    try:
        item = db.get(NewsItem, item_id)
        if item is None:
            return
        for key, value in fields.items():
            setattr(item, key, value)
        db.commit()
    finally:
        db.close()


# -- Fetch: feed -> deduplicated NewsItem rows ------------------------


def _insert_entries(db, source: NewsSource, entries: list[FetchedEntry]) -> tuple[int, int]:
    """Returns (new_items, duplicates). Dedupes within this source on guid
    and across all sources on the title fingerprint.
    """
    existing_guids = {
        row[0] for row in db.execute(
            select(NewsItem.guid).where(NewsItem.source_id == source.id)
        )
    }
    seen_fingerprints = {
        row[0] for row in db.execute(select(NewsItem.fingerprint).distinct())
    }

    new_count = 0
    dup_count = 0
    for entry in entries:
        if entry.guid in existing_guids or entry.fingerprint in seen_fingerprints:
            dup_count += 1
            continue
        db.add(NewsItem(
            source_id=source.id,
            guid=entry.guid,
            fingerprint=entry.fingerprint,
            title=entry.title,
            summary=entry.summary,
            link=entry.link,
            image_url=entry.image_url,
            published_at=entry.published_at,
            status="new",
        ))
        existing_guids.add(entry.guid)
        seen_fingerprints.add(entry.fingerprint)
        new_count += 1
    return new_count, dup_count


def fetch_source(source_id: int) -> FetchResult:
    """Fetch one source's feed and store any new items. Never raises for a
    feed/network problem -- records it on NewsSource.last_error and returns
    a FetchResult carrying the message.
    """
    db = SessionLocal()
    try:
        source = db.get(NewsSource, source_id)
        if source is None:
            raise NotFoundError("News source", source_id)

        result = FetchResult(source_id=source.id, source_name=source.name)
        try:
            entries = fetch_feed(source.feed_url)
        except FeedFetchError as exc:
            source.last_error = str(exc)
            source.last_fetched_at = _utcnow()
            db.commit()
            result.error = str(exc)
            return result

        result.fetched = len(entries)
        result.new_items, result.duplicates = _insert_entries(db, source, entries)
        source.last_error = None
        source.last_fetched_at = _utcnow()
        db.commit()
        return result
    finally:
        db.close()


def fetch_all_enabled_sources() -> list[FetchResult]:
    """Called by the router's fetch-all endpoint and the background poll
    loop. Each source is fetched independently -- one failing feed never
    stops the rest.
    """
    results: list[FetchResult] = []
    for source in list_sources():
        if not source.enabled:
            continue
        try:
            results.append(fetch_source(source.id))
        except Exception:  # noqa: BLE001 -- a bad source must never abort the sweep
            logger.exception("News fetch failed for source %s", source.id)
            results.append(FetchResult(source_id=source.id, source_name=source.name, error="Unexpected fetch error"))
    return results
