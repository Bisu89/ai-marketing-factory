import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_path_segment(name: str) -> str:
    cleaned = _ILLEGAL_CHARS.sub("_", name).strip(" .")
    return cleaned or "unknown"


@dataclass
class VideoMetadata:
    platform: str
    video_id: str
    channel_name: str
    title: str
    original_url: str
    thumbnail_url: str | None
    views: int | None
    likes: int | None
    duration_sec: int | None
    upload_date: str | None
    tags: list[str]


def build_video_dir(library_dir: Path, metadata: VideoMetadata) -> Path:
    return (
        library_dir
        / sanitize_path_segment(metadata.platform)
        / sanitize_path_segment(metadata.channel_name)
        / sanitize_path_segment(metadata.video_id)
    )


def _download_thumbnail(url: str, destination: Path) -> bool:
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=15.0) as response:
            response.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
        return True
    except Exception:
        logger.warning("Failed to download thumbnail from %s", url, exc_info=True)
        destination.unlink(missing_ok=True)
        return False


def organize_completed_download(
    video_path: Path,
    library_dir: Path,
    metadata: VideoMetadata,
    downloaded_at: datetime,
) -> Path:
    """Moves a completed download into library_dir/<platform>/<channel_name>/<video_id>/
    as video.mp4, fetches thumbnail.jpg (best-effort), and writes metadata.json.
    Returns the final path of video.mp4.
    """
    # Order matters: write everything that can fail (thumbnail, metadata.json)
    # *before* moving the video file. If anything raises, the video stays at its
    # original staging path and the job's destination_path is still valid for a retry.
    video_dir = build_video_dir(library_dir, metadata)
    video_dir.mkdir(parents=True, exist_ok=True)

    if metadata.thumbnail_url:
        _download_thumbnail(metadata.thumbnail_url, video_dir / "thumbnail.jpg")

    metadata_json = {
        "Title": metadata.title,
        "Author": metadata.channel_name,
        "Platform": metadata.platform,
        "Views": metadata.views,
        "Like": metadata.likes,
        "Duration": metadata.duration_sec,
        "Upload Date": metadata.upload_date,
        "Original URL": metadata.original_url,
        "Downloaded Date": downloaded_at.isoformat(),
        "Tags": metadata.tags,
    }
    with open(video_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata_json, f, ensure_ascii=False, indent=2)

    final_video_path = video_dir / "video.mp4"
    shutil.move(str(video_path), str(final_video_path))

    return final_video_path
