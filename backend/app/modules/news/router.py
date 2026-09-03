"""News source/item CRUD + feed fetching. The News -> Factory pipeline
(draft scripts, create batch) lives in the composition root
app/api/v1/endpoints/news_pipeline.py, not here -- this module must never
import app.modules.beat / app.modules.batch / app.modules.ai.
"""

from fastapi import APIRouter, Query

from app.modules.news import service
from app.modules.news.schemas import (
    FetchAllResponse,
    FetchResult,
    NewsItemListResponse,
    NewsItemOut,
    NewsItemUpdateIn,
    NewsSourceCreateIn,
    NewsSourceOut,
    NewsSourceUpdateIn,
)

router = APIRouter()


def _source_out(source, pending: dict[int, int] | None = None) -> NewsSourceOut:
    out = NewsSourceOut.model_validate(source)
    if pending is not None:
        out.pending_items = pending.get(source.id, 0)
    return out


def _item_out(item) -> NewsItemOut:
    out = NewsItemOut.model_validate(item)
    out.source_name = item.source.name if item.source is not None else None
    return out


# -- Sources -----------------------------------------------------------


@router.get("/news/sources", response_model=list[NewsSourceOut])
def list_news_sources():
    pending = service.pending_counts_by_source()
    return [_source_out(s, pending) for s in service.list_sources()]


@router.post("/news/sources", response_model=NewsSourceOut, status_code=201)
def create_news_source(payload: NewsSourceCreateIn):
    source = service.create_source(
        name=payload.name, feed_url=payload.feed_url, category=payload.category,
        language=payload.language, enabled=payload.enabled,
    )
    return _source_out(source)


@router.patch("/news/sources/{source_id}", response_model=NewsSourceOut)
def update_news_source(source_id: int, payload: NewsSourceUpdateIn):
    source = service.update_source(
        source_id,
        name=payload.name, feed_url=payload.feed_url, category=payload.category,
        language=payload.language, enabled=payload.enabled,
    )
    return _source_out(source)


@router.delete("/news/sources/{source_id}", status_code=204)
def delete_news_source(source_id: int):
    service.delete_source(source_id)


@router.post("/news/sources/{source_id}/fetch", response_model=FetchResult)
def fetch_news_source(source_id: int):
    return service.fetch_source(source_id)


@router.post("/news/fetch-all", response_model=FetchAllResponse)
def fetch_all_news_sources():
    results = service.fetch_all_enabled_sources()
    return FetchAllResponse(results=results, total_new_items=sum(r.new_items for r in results))


# -- Items -----------------------------------------------------------


@router.get("/news/items", response_model=NewsItemListResponse)
def list_news_items(
    status: str | None = None,
    source_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    items, total = service.list_items(status=status, source_id=source_id, page=page, page_size=page_size)
    return NewsItemListResponse(
        items=[_item_out(i) for i in items], total=total, page=page, page_size=page_size
    )


@router.get("/news/items/{item_id}", response_model=NewsItemOut)
def get_news_item(item_id: int):
    return _item_out(service.get_item(item_id))


@router.patch("/news/items/{item_id}", response_model=NewsItemOut)
def update_news_item(item_id: int, payload: NewsItemUpdateIn):
    item = service.update_item(item_id, status=payload.status, script_text=payload.script_text)
    return _item_out(service.get_item(item.id))
