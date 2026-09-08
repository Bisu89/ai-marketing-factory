"""Persistence + orchestration glue for the Radar.

"SessionLocal per call" shape (same as app.modules.news.service) -- these
functions are called only from request handlers today, but keeping them
session-self-contained matches the rest of the module conventions and
leaves the door open for a background "scheduled radar" later.

A short-TTL in-process cache (brief section 28) keys on
(sorted platforms, normalized query, sort, max_age_days) so re-running the
same search within the window replays the stored rows instead of hitting
Reddit / YouTube again.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import SessionLocal
from app.modules.discovery.contracts import (
    DOWNLOAD_ALLOWED,
    DOWNLOAD_PERMISSION_REQUIRED,
    DOWNLOAD_UNSUPPORTED,
    DOWNLOADABLE_RIGHTS,
    PLATFORM_REDDIT,
    PLATFORM_YOUTUBE,
    VideoResult,
)
from app.modules.discovery.keywords import keywords_from_result
from app.modules.discovery.models import DiscoveryResult, DiscoverySearch
from app.modules.discovery.orchestrator import SearchOrchestrator, SearchOutput

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 900  # 15 minutes
_cache: dict[str, tuple[float, int]] = {}  # key -> (expires_at, search_id)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _cache_key(query: str, platforms: list[str] | None, sort: str, max_age_days: int | None) -> str:
    plats = ",".join(sorted(platforms)) if platforms else "all"
    return f"{plats}|{query.lower().strip()}|{sort}|{max_age_days}"


def _download_capability(rights_status: str, platform: str) -> str:
    """What the card's action button should be (brief section 22).

    Downloading is only offered when BOTH the rights permit it AND an
    engine has a legitimate fetch path. In Phase 1 that means: YouTube
    Creative Commons (yt-dlp can fetch it) and Reddit-hosted video that is
    somehow already cleared -- everything else is PERMISSION_REQUIRED.
    """
    if rights_status not in DOWNLOADABLE_RIGHTS:
        return DOWNLOAD_PERMISSION_REQUIRED
    if platform in (PLATFORM_YOUTUBE, PLATFORM_REDDIT):
        return DOWNLOAD_ALLOWED
    return DOWNLOAD_UNSUPPORTED


# -- run + persist ---------------------------------------------------


def run_search(
    query: str,
    *,
    platforms: list[str] | None = None,
    sort: str = "best",
    max_age_days: int | None = 365,
    limit_per_query: int = 15,
    orchestrator: SearchOrchestrator | None = None,
    use_cache: bool = True,
) -> int:
    """Execute a search, persist it, return the new (or cached) search id."""
    key = _cache_key(query, platforms, sort, max_age_days)
    if use_cache:
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            logger.info("discovery: cache hit for %r", key)
            return hit[1]

    orch = orchestrator or SearchOrchestrator()
    output = orch.search(
        query,
        platforms=platforms,
        sort=sort,
        max_age_days=max_age_days,
        limit_per_query=limit_per_query,
    )
    search_id = _persist(output)
    _cache[key] = (time.time() + CACHE_TTL_SECONDS, search_id)
    return search_id


def _persist(output: SearchOutput) -> int:
    db = SessionLocal()
    try:
        search = DiscoverySearch(
            query=output.query,
            normalized_query=output.normalized_query,
            expanded_queries_json=json.dumps(output.expanded_queries),
            engine_statuses_json=json.dumps(
                [
                    {
                        "platform": s.platform,
                        "status": s.status,
                        "result_count": s.result_count,
                        "error": s.error,
                    }
                    for s in output.engine_statuses
                ]
            ),
            result_count=output.unique_count,
        )
        db.add(search)
        db.flush()

        for r in output.results:
            db.add(_result_row(search.id, r))

        db.commit()
        return search.id
    finally:
        db.close()


def _result_row(search_id: int, r: VideoResult) -> DiscoveryResult:
    return DiscoveryResult(
        search_id=search_id,
        platform=r.platform,
        source_url=r.source_url,
        title=r.title,
        description=r.description,
        thumbnail_url=r.thumbnail_url,
        creator_name=r.creator_name,
        creator_url=r.creator_url,
        published_at=r.published_at,
        duration_sec=r.duration_sec,
        views=r.views,
        likes=r.likes,
        comments=r.comments,
        shares=r.shares,
        width=r.width,
        height=r.height,
        content_tags_json=json.dumps(r.content_tags),
        also_on_json=json.dumps(r.also_on),
        relevance_score=r.relevance_score,
        engagement_score=r.engagement_score,
        recency_score=r.recency_score,
        short_form_score=r.short_form_score,
        content_signal_score=r.content_signal_score,
        viral_score=r.viral_score,
        rights_status=r.rights_status,
        attribution=r.attribution,
        download_capability=_download_capability(r.rights_status, r.platform),
    )


# -- read ----------------------------------------------------------


def get_search(search_id: int) -> tuple[DiscoverySearch, list[DiscoveryResult]]:
    db = SessionLocal()
    try:
        search = db.get(DiscoverySearch, search_id)
        if search is None:
            raise NotFoundError("Search", search_id)
        results = (
            db.query(DiscoveryResult)
            .filter(DiscoveryResult.search_id == search_id)
            .order_by(DiscoveryResult.viral_score.desc())
            .all()
        )
        db.expunge_all()
        return search, results
    finally:
        db.close()


def list_searches(limit: int = 30) -> list[DiscoverySearch]:
    db = SessionLocal()
    try:
        rows = (
            db.query(DiscoverySearch)
            .order_by(DiscoverySearch.created_at.desc())
            .limit(limit)
            .all()
        )
        db.expunge_all()
        return rows
    finally:
        db.close()


def get_result(result_id: int) -> DiscoveryResult:
    db = SessionLocal()
    try:
        row = db.get(DiscoveryResult, result_id)
        if row is None:
            raise NotFoundError("Result", result_id)
        db.expunge(row)
        return row
    finally:
        db.close()


def list_saved() -> list[DiscoveryResult]:
    db = SessionLocal()
    try:
        rows = (
            db.query(DiscoveryResult)
            .filter(DiscoveryResult.saved_at.isnot(None))
            .order_by(DiscoveryResult.saved_at.desc())
            .all()
        )
        for row in rows:
            _ = row.search.query  # eager-load before expunge
        db.expunge_all()
        return rows
    finally:
        db.close()


# -- mutate --------------------------------------------------------


def save_result(result_id: int, *, collection: str, notes: str | None) -> DiscoveryResult:
    db = SessionLocal()
    try:
        row = db.get(DiscoveryResult, result_id)
        if row is None:
            raise NotFoundError("Result", result_id)
        row.saved_at = _utcnow()
        row.collection = collection
        row.notes = notes
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    finally:
        db.close()


def unsave_result(result_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(DiscoveryResult, result_id)
        if row is None:
            raise NotFoundError("Result", result_id)
        row.saved_at = None
        row.collection = None
        db.commit()
    finally:
        db.close()


# -- find more like this (brief section 25, no AI) ----------------


def find_similar(
    result_id: int,
    *,
    orchestrator: SearchOrchestrator | None = None,
) -> tuple[list[str], int]:
    row = get_result(result_id)
    tags = json.loads(row.content_tags_json or "[]")
    keywords = keywords_from_result(row.title, tags, row.description)
    if not keywords:
        raise ValidationError("Could not derive any search terms from this result.")
    query = " ".join(keywords[:3])
    search_id = run_search(
        query,
        platforms=None,
        sort="best",
        orchestrator=orchestrator,
        use_cache=False,
    )
    return keywords, search_id


def clear_cache() -> None:
    _cache.clear()
