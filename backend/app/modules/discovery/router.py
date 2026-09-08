"""Viral Source Radar API (brief section 30).

  POST   /discover                     run a search
  GET    /discover                     recent searches
  GET    /discover/saved               shortlisted results (Save system)
  GET    /discover/{id}                replay a stored search
  POST   /discover/results/{id}/save   add to a collection
  DELETE /discover/results/{id}/save   remove from shortlist
  POST   /discover/results/{id}/find-similar

This module is self-contained -- it never imports app.modules.beat /
batch / ai. Turning a saved source into content is a future composition
root's job.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from app.modules.discovery import service
from app.modules.discovery.contracts import ALL_PLATFORMS
from app.modules.discovery.models import DiscoveryResult, DiscoverySearch
from app.modules.discovery.schemas import (
    DEFAULT_COLLECTIONS,
    EngineStatusOut,
    FindSimilarOut,
    ResultOut,
    SavedResultOut,
    SaveResultOut,
    SaveResultRequest,
    ScoreBreakdown,
    SearchRequest,
    SearchResultOut,
    SearchSummaryOut,
)

router = APIRouter()


def _aspect_ratio(w: int | None, h: int | None) -> float | None:
    if not w or not h:
        return None
    return round(w / h, 3)


def _result_out(row: DiscoveryResult) -> ResultOut:
    return ResultOut(
        id=row.id,
        platform=row.platform,
        source_url=row.source_url,
        title=row.title,
        description=row.description,
        thumbnail_url=row.thumbnail_url,
        creator_name=row.creator_name,
        creator_url=row.creator_url,
        published_at=row.published_at,
        duration_sec=row.duration_sec,
        views=row.views,
        likes=row.likes,
        comments=row.comments,
        shares=row.shares,
        width=row.width,
        height=row.height,
        aspect_ratio=_aspect_ratio(row.width, row.height),
        content_tags=json.loads(row.content_tags_json or "[]"),
        also_on=json.loads(row.also_on_json or "[]"),
        viral_score=row.viral_score,
        score_breakdown=ScoreBreakdown(
            relevance=row.relevance_score,
            engagement=row.engagement_score,
            recency=row.recency_score,
            short_form=row.short_form_score,
            content_signals=row.content_signal_score,
        ),
        rights_status=row.rights_status,
        attribution=row.attribution,
        download_capability=row.download_capability,
        saved_video_id=row.saved_video_id,
        collection=row.collection,
        notes=row.notes,
    )


def _search_out(search: DiscoverySearch, results: list[DiscoveryResult]) -> SearchResultOut:
    statuses = json.loads(search.engine_statuses_json or "[]")
    return SearchResultOut(
        id=search.id,
        query=search.query,
        normalized_query=search.normalized_query,
        expanded_queries=json.loads(search.expanded_queries_json or "[]"),
        engine_statuses=[EngineStatusOut(**s) for s in statuses],
        total_before_dedup=len(results),
        unique_count=search.result_count,
        results=[_result_out(r) for r in results],
        created_at=search.created_at,
    )


@router.get("/discover/collections", response_model=list[str])
def list_collections() -> list[str]:
    return list(DEFAULT_COLLECTIONS)


@router.get("/discover/platforms", response_model=list[str])
def list_platforms() -> list[str]:
    return list(ALL_PLATFORMS)


@router.post("/discover", response_model=SearchResultOut)
def create_search(payload: SearchRequest) -> SearchResultOut:
    search_id = service.run_search(
        payload.query,
        platforms=payload.platforms,
        sort=payload.sort,
        max_age_days=payload.max_age_days,
        limit_per_query=payload.limit_per_query,
    )
    search, results = service.get_search(search_id)
    return _search_out(search, results)


@router.get("/discover", response_model=list[SearchSummaryOut])
def recent_searches(limit: int = Query(30, ge=1, le=100)) -> list[SearchSummaryOut]:
    return [
        SearchSummaryOut(
            id=s.id, query=s.query, result_count=s.result_count, created_at=s.created_at
        )
        for s in service.list_searches(limit)
    ]


@router.get("/discover/saved", response_model=list[SavedResultOut])
def saved_results() -> list[SavedResultOut]:
    out: list[SavedResultOut] = []
    for row in service.list_saved():
        base = _result_out(row).model_dump()
        out.append(
            SavedResultOut(
                **base,
                search_id=row.search_id,
                query=row.search.query,
                discovered_at=row.discovered_at,
            )
        )
    return out


@router.get("/discover/{search_id}", response_model=SearchResultOut)
def get_search(search_id: int) -> SearchResultOut:
    search, results = service.get_search(search_id)
    return _search_out(search, results)


@router.post("/discover/results/{result_id}/save", response_model=SaveResultOut)
def save_result(result_id: int, payload: SaveResultRequest) -> SaveResultOut:
    row = service.save_result(result_id, collection=payload.collection, notes=payload.notes)
    return SaveResultOut(
        result_id=row.id, saved=True, collection=row.collection, notes=row.notes
    )


@router.delete("/discover/results/{result_id}/save", status_code=204)
def unsave_result(result_id: int):
    service.unsave_result(result_id)


@router.post("/discover/results/{result_id}/find-similar", response_model=FindSimilarOut)
def find_similar(result_id: int) -> FindSimilarOut:
    keywords, search_id = service.find_similar(result_id)
    search, results = service.get_search(search_id)
    return FindSimilarOut(keywords=keywords, search=_search_out(search, results))
