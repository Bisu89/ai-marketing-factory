from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import FileOperationError
from app.db.session import get_db
from app.modules.asset.import_service import (
    cancel_import_job,
    create_import_job,
    get_import_job,
    rescan_library,
    start_import_job_in_background,
)
from app.modules.asset.schemas import (
    AssetImportJobOut,
    AssetImportRequest,
    AssetOut,
    AssetRegisterIn,
    RescanResult,
    asset_to_out,
    import_job_to_out,
)
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
    orientation: str | None = None,
    category: str | None = None,
    emotion: str | None = None,
    source: str | None = None,
    missing_only: bool = False,
    service: AssetService = Depends(get_asset_service),
):
    # q is a comma-separated keyword list ("woman,emotional,portrait") --
    # simple query-string shape, no repeated-param parsing needed for a
    # local desktop tool with no client generated yet.
    query_terms = [term for term in q.split(",")] if q else None
    assets = service.search(
        query=query_terms,
        asset_type=asset_type,
        orientation=orientation,
        category=category,
        emotion=emotion,
        source=source,
        missing_only=missing_only,
    )
    return [asset_to_out(asset) for asset in assets]


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


@router.get("/assets/{asset_id}/thumbnail")
def get_asset_thumbnail(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    # Same "not reachable through /media" reasoning as get_asset_file above
    # -- thumbnails live under library_dir/_asset/thumbnails (this module's
    # own artifact area, per app/modules/README.md's "own artifact files"
    # convention), served here rather than through the generic mount so a
    # missing thumbnail (not every asset has one -- e.g. one registered
    # through the old bare POST /assets) raises a clear error instead of a
    # bare static-file 404.
    asset = service.get(asset_id)
    if not asset.thumbnail_path:
        raise FileOperationError(f"Asset {asset_id} has no thumbnail.")
    path = Path(asset.thumbnail_path)
    if not path.is_file():
        raise FileOperationError(f"Thumbnail file not found on disk: {path}")
    return FileResponse(path)


# -- Bulk local import (Task 15 -- see docs/features/41-local-asset-ingestion.md) --
#
# Lives entirely inside this module (unlike Task 13's batch orchestration,
# which needed a composition-root file) since ingestion never needs to know
# about any other module -- it only reads local files and writes Asset/
# AssetImportJob rows, both owned right here.


@router.post("/assets/import", response_model=AssetImportJobOut, status_code=201)
def import_assets(
    payload: AssetImportRequest,
    settings: Settings = Depends(get_settings),
):
    job_id = create_import_job(paths=payload.paths, folder=payload.folder, recursive=payload.recursive)
    start_import_job_in_background(job_id, Path(settings.library_dir))
    return import_job_to_out(get_import_job(job_id))


@router.get("/assets/import/{job_id}", response_model=AssetImportJobOut)
def get_asset_import_job(job_id: int):
    return import_job_to_out(get_import_job(job_id))


@router.post("/assets/import/{job_id}/cancel", response_model=AssetImportJobOut)
def cancel_asset_import_job(job_id: int):
    return import_job_to_out(cancel_import_job(job_id))


@router.post("/assets/rescan", response_model=RescanResult)
def rescan_assets(settings: Settings = Depends(get_settings)):
    return RescanResult(**rescan_library(Path(settings.library_dir)))
