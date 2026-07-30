from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.models.video import Video


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    platform: str = Field(validation_alias="platform_name")
    external_id: str
    channel_id: int
    channel_name: str
    title: str
    original_url: str
    thumbnail_url: str | None
    thumbnail_path: str | None
    video_path: str | None
    # Browser-loadable URLs (served via the /media static mount), derived from
    # thumbnail_path/video_path -- those two stay as raw server filesystem
    # paths for "Folder Path" display / Open Folder, since a <img>/<video> tag
    # can't load a filesystem path directly.
    thumbnail_media_url: str | None = None
    video_media_url: str | None = None
    views: int | None
    likes: int | None
    duration_sec: int | None
    upload_date: str | None

    status: str
    category_id: int | None
    notes: str | None
    resolution: str | None
    filesize_bytes: int | None
    file_hash: str | None
    is_favorite: bool
    tags: list[str] = Field(default_factory=list, validation_alias="tag_names")

    is_downloaded: bool
    downloaded_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _to_media_url(path_str: str | None, library_dir: Path) -> str | None:
    if not path_str:
        return None
    try:
        rel = Path(path_str).resolve().relative_to(library_dir.resolve())
    except ValueError:
        return None
    return "/media/" + rel.as_posix()


def video_to_out(video: Video, library_dir: Path) -> VideoOut:
    base = VideoOut.model_validate(video)
    return base.model_copy(
        update={
            "thumbnail_media_url": _to_media_url(video.thumbnail_path, library_dir),
            "video_media_url": _to_media_url(video.video_path, library_dir),
        }
    )


class VideoListResponse(BaseModel):
    items: list[VideoOut]
    total: int
    page: int
    page_size: int


class VideoUpdateIn(BaseModel):
    status: str | None = None
    category_id: int | None = None
    notes: str | None = None


class VideoImportIn(BaseModel):
    file_path: str
    platform: str
    channel_name: str
    title: str
    external_id: str | None = None
    category_id: int | None = None
    notes: str | None = None
    tags: list[str] = []
