import re

import yt_dlp

from app.schemas.detect import CollectionResultOut, SingleVideoResultOut, VideoInfoOut

_YOUTUBE_RE = re.compile(r"youtube\.com|youtu\.be", re.IGNORECASE)
_TIKTOK_RE = re.compile(r"tiktok\.com", re.IGNORECASE)
_FACEBOOK_RE = re.compile(r"facebook\.com|fb\.watch", re.IGNORECASE)
_INSTAGRAM_RE = re.compile(r"instagram\.com", re.IGNORECASE)
_CHANNEL_RE = re.compile(r"/channel/|/@|/c/", re.IGNORECASE)


class DetectionError(Exception):
    """Raised when yt-dlp fails to extract any information for a URL."""


def _detect_platform(url: str) -> str:
    if _YOUTUBE_RE.search(url):
        return "youtube"
    if _TIKTOK_RE.search(url):
        return "tiktok"
    if _FACEBOOK_RE.search(url):
        return "facebook"
    if _INSTAGRAM_RE.search(url):
        return "instagram"
    return "unknown"


def _best_thumbnail(entry: dict) -> str:
    thumbnail = entry.get("thumbnail")
    if thumbnail:
        return thumbnail
    thumbnails = entry.get("thumbnails") or []
    return thumbnails[-1]["url"] if thumbnails else ""


def _to_video_info(entry: dict, fallback_author: str) -> VideoInfoOut:
    return VideoInfoOut(
        id=str(entry.get("id") or ""),
        title=entry.get("title") or "Untitled",
        thumbnailUrl=_best_thumbnail(entry),
        author=entry.get("channel") or entry.get("uploader") or fallback_author or "",
        views=entry.get("view_count") or 0,
        uploadDate=entry.get("upload_date") or "",
        durationSec=int(entry.get("duration") or 0),
        originalUrl=entry.get("webpage_url") or entry.get("url") or "",
    )


def detect_url(url: str) -> SingleVideoResultOut | CollectionResultOut:
    platform = _detect_platform(url)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DetectionError(str(exc)) from exc

    if info is None:
        raise DetectionError("Không lấy được thông tin từ URL này")

    if info.get("_type") == "playlist":
        content_type = "channel" if _CHANNEL_RE.search(url) else "playlist"
        author = info.get("channel") or info.get("uploader") or info.get("title") or ""
        entries = [entry for entry in (info.get("entries") or []) if entry]
        return CollectionResultOut(
            contentType=content_type,
            platform=platform,
            title=info.get("title") or author or "Untitled",
            author=author,
            videos=[_to_video_info(entry, author) for entry in entries],
        )

    return SingleVideoResultOut(
        contentType="video",
        platform=platform,
        video=_to_video_info(info, info.get("channel") or info.get("uploader") or ""),
    )
