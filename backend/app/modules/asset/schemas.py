from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.asset.ingest import classify_portrait_suitability
from app.modules.asset.models import ASSET_TYPES, Asset, AssetImportJob


class AssetRegisterIn(BaseModel):
    filename: str
    path: str
    type: str
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    tags: list[str] = []
    source: str = "upload"
    source_ref: str | None = None
    extra_metadata: dict[str, Any] | None = None

    @field_validator("filename")
    @classmethod
    def _filename_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("filename must not be blank")
        return value

    @field_validator("path")
    @classmethod
    def _path_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path must not be blank")
        return value

    @field_validator("type")
    @classmethod
    def _valid_type(cls, value: str) -> str:
        if value not in ASSET_TYPES:
            raise ValueError(f"Invalid type {value!r}, must be one of {ASSET_TYPES}")
        return value

    @field_validator("width", "height")
    @classmethod
    def _dimension_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("width/height must be > 0 when provided")
        return value

    @field_validator("duration_sec")
    @classmethod
    def _duration_positive(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("duration_sec must be > 0 when provided")
        return value


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    path: str
    type: str
    width: int | None
    height: int | None
    duration_sec: float | None
    filesize_bytes: int | None
    tags: list[str]
    source: str
    source_ref: str | None
    extra_metadata: dict[str, Any] | None
    is_ready: bool
    created_at: datetime

    # -- Task 15 (see docs/features/41-local-asset-ingestion.md) -- all
    # default so a pre-Task-15 AssetOut shape (e.g. the checked-in
    # examples/video_factory/assets.json golden sample) still validates
    # with zero migration, same convention as BeatPlan.config's own
    # default_factory before it.
    content_hash: str | None = None
    # `orientation`/`status` below are the *computed* (Asset.orientation_computed/
    # effective_status), not the raw stored columns -- always geometry/
    # filesystem-consistent, never stale (see those properties' own
    # docstrings on Asset).
    orientation: str | None = None
    category: str | None = None
    emotion: str | None = None
    status: str = "ACTIVE"
    thumbnail_path: str | None = None
    aspect_ratio: float | None = None
    # Metadata guidance only (section 34) -- null when width/height are
    # unknown (e.g. a legacy asset registered without them).
    portrait_suitability: str | None = None


def asset_to_out(asset: Asset) -> AssetOut:
    return AssetOut(
        id=asset.id,
        filename=asset.filename,
        path=asset.path,
        type=asset.type,
        width=asset.width,
        height=asset.height,
        duration_sec=asset.duration_sec,
        filesize_bytes=asset.filesize_bytes,
        tags=asset.tags,
        source=asset.source,
        source_ref=asset.source_ref,
        extra_metadata=asset.extra_metadata,
        is_ready=asset.is_ready,
        created_at=asset.created_at,
        content_hash=asset.content_hash,
        orientation=asset.orientation_computed,
        category=asset.category,
        emotion=asset.emotion,
        status=asset.effective_status,
        thumbnail_path=asset.thumbnail_path,
        aspect_ratio=asset.aspect_ratio,
        portrait_suitability=classify_portrait_suitability(asset.width, asset.height),
    )


# -- Import jobs (Task 15) --------------------------------------------------


class AssetImportRequest(BaseModel):
    """Either `paths` (explicit files -- the "Add Files" flow) or `folder`
    (recursively walked -- "Import Folder") must be given, never both. Paths
    are typed/pasted, not picked via a native OS dialog -- matching this
    app's existing convention (see e.g. VideoFactoryPage's music/output-dir
    path inputs, and AssetBrowserModal's own "paste a file path to
    register" flow) rather than introducing browser file-picker plumbing
    this desktop-local app has never used anywhere else.
    """

    paths: list[str] | None = None
    folder: str | None = None
    recursive: bool = True

    @field_validator("paths")
    @classmethod
    def _paths_not_empty_list(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) == 0:
            raise ValueError("paths must not be an empty list -- omit it entirely instead")
        return value


class FailedImportFile(BaseModel):
    path: str
    reason: str


class AssetImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    source_label: str
    total_files: int
    processed_files: int
    imported_count: int
    duplicate_count: int
    failed_count: int
    current_file: str | None
    failed_files: list[FailedImportFile] = Field(default_factory=list)
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    created_at: datetime


def import_job_to_out(job: AssetImportJob) -> AssetImportJobOut:
    return AssetImportJobOut.model_validate(job)


class RescanResult(BaseModel):
    checked: int
    now_missing: int
    now_active: int
    now_invalid: int
    unchanged: int
