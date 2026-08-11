from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.asset.models import ASSET_TYPES, Asset


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


def asset_to_out(asset: Asset) -> AssetOut:
    return AssetOut.model_validate(asset)
