from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.exceptions import FileOperationError
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


@router.get("/assets/{asset_id}/file")
def get_asset_file(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    # Asset.path can point anywhere on disk (it's a reference to a file the
    # user picked, not something this app owns a copy of -- see
    # app/modules/asset/models.py), so it can't be reached through the
    # existing /media StaticFiles mount (that only serves paths under
    # library_dir). This is the one place that actually needs the bytes,
    # not just the metadata `get_asset` above already returns.
    #
    # Not type-restricted (unlike app.modules.beat's motion-render path,
    # which uses service.get_image() because only an image can actually be
    # rendered) -- this is a generic "give me the bytes to preview" route,
    # used for both image previews (Task 32) and audio previews (Task 36's
    # narration/music asset pickers). Any registered asset is previewable.
    asset = service.get(asset_id)
    path = Path(asset.path)
    if not path.is_file():
        raise FileOperationError(f"Asset file not found on disk: {path}")
    return FileResponse(path)


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    service.delete(asset_id)
