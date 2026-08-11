from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.asset.schemas import AssetOut, AssetRegisterIn, asset_to_out
from app.modules.asset.service import AssetService

router = APIRouter()


def get_asset_service(db: Session = Depends(get_db)) -> AssetService:
    return AssetService(db)


@router.post("/assets", response_model=AssetOut, status_code=201)
def register_asset(
    payload: AssetRegisterIn,
    service: AssetService = Depends(get_asset_service),
):
    return asset_to_out(service.register(payload))


@router.get("/assets", response_model=list[AssetOut])
def search_assets(
    q: str | None = None,
    asset_type: str | None = None,
    service: AssetService = Depends(get_asset_service),
):
    # q is a comma-separated keyword list ("woman,emotional,portrait") --
    # simple query-string shape, no repeated-param parsing needed for a
    # local desktop tool with no client generated yet.
    query_terms = [term for term in q.split(",")] if q else None
    return [asset_to_out(asset) for asset in service.search(query=query_terms, asset_type=asset_type)]


@router.get("/assets/{asset_id}", response_model=AssetOut)
def get_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    return asset_to_out(service.get(asset_id))


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    service.delete(asset_id)
