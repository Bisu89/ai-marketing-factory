import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import FileOperationError, NotFoundError, ValidationError
from app.models.download_history import DownloadHistory
from app.models.download_task import DownloadTask
from app.models.video import VIDEO_STATUSES, Video
from app.services.library import catalog
from app.services.library.organizer import VideoMetadata, organize_imported_file
from app.services.library.repository import (
    CategoryRepository,
    EmotionRepository,
    TagRepository,
    VideoFilters,
    VideoRepository,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoLibraryService:
    def __init__(self, db: Session, library_dir: Path):
        self.db = db
        self.library_dir = library_dir
        self.videos = VideoRepository(db)
        self.tags = TagRepository(db)
        self.categories = CategoryRepository(db)
        self.emotions = EmotionRepository(db)

    def list_videos(
        self,
        search: str | None = None,
        platform: str | None = None,
        status: str | None = None,
        category_id: int | None = None,
        emotion_id: int | None = None,
        tag: str | None = None,
        favorite: bool | None = None,
        duration: str | None = None,
        resolution: str | None = None,
        sort: str = "newest",
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Video], int]:
        filters = VideoFilters(
            search=search,
            platform=platform,
            status=status,
            category_id=category_id,
            emotion_id=emotion_id,
            tag=tag,
            favorite=favorite,
            duration=duration,
            resolution=resolution,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        return self.videos.list(filters)

    def get_video(self, video_id: int) -> Video:
        video = self.videos.get(video_id)
        if video is None:
            raise NotFoundError("Video", video_id)
        return video

    def open_folder(self, video_id: int) -> None:
        """Reveals the video's library folder in the OS file explorer. Safe
        from command injection: video_path is server-controlled (set by the
        organizer, never taken verbatim from client input), and every branch
        passes a Path as an argument list / dedicated API, never a shell string.
        """
        video = self.get_video(video_id)
        if not video.video_path:
            raise FileOperationError("This video has no folder yet")

        folder = Path(video.video_path).parent
        if not folder.exists():
            raise FileOperationError(f"Folder not found: {folder}")

        try:
            if sys.platform == "win32":
                os.startfile(folder)  # noqa: S606 -- Windows-only, path is server-controlled
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            raise FileOperationError(f"Could not open folder {folder}: {exc}") from exc

    def update_video(
        self,
        video_id: int,
        status: str | None = None,
        category_id: int | None = None,
        emotion_id: int | None = None,
        notes: str | None = None,
    ) -> Video:
        video = self.get_video(video_id)

        if status is not None:
            if status not in VIDEO_STATUSES:
                raise ValidationError(f"Invalid status {status!r}, must be one of {VIDEO_STATUSES}")
            video.status = status

        if category_id is not None:
            if self.categories.get(category_id) is None:
                raise NotFoundError("Category", category_id)
            video.category_id = category_id

        if emotion_id is not None:
            if self.emotions.get(emotion_id) is None:
                raise NotFoundError("Emotion", emotion_id)
            video.emotion_id = emotion_id

        if notes is not None:
            video.notes = notes

        return self.videos.save(video)

    def set_favorite(self, video_id: int, favorite: bool) -> Video:
        video = self.get_video(video_id)
        self.videos.set_favorite(video_id, favorite)
        self.db.refresh(video)
        return video

    def add_tags(self, video_id: int, tag_names: list[str]) -> Video:
        video = self.get_video(video_id)
        for name in tag_names:
            name = name.strip()
            if not name:
                continue
            tag = self.tags.get_by_name(name)
            if tag is None:
                tag = self.tags.create(name)
            self.tags.add_to_video(video_id, tag.id)
        self.db.refresh(video)
        return video

    def remove_tag(self, video_id: int, tag_id: int) -> Video:
        video = self.get_video(video_id)
        self.tags.remove_from_video(video_id, tag_id)
        self.db.refresh(video)
        return video

    def delete_video(self, video_id: int, hard: bool) -> None:
        video = self.get_video(video_id)

        if not hard:
            video.status = "deleted"
            self.videos.save(video)
            return

        if video.video_path:
            folder = Path(video.video_path).parent
            try:
                if folder.exists():
                    shutil.rmtree(folder)
            except OSError as exc:
                raise FileOperationError(f"Could not delete video files at {folder}: {exc}") from exc

        self.db.query(DownloadHistory).filter(DownloadHistory.video_id == video_id).delete()
        self.db.query(DownloadTask).filter(DownloadTask.video_id == video_id).delete()
        self.videos.delete(video)

    def import_existing_file(
        self,
        file_path: str,
        platform: str,
        channel_name: str,
        title: str,
        external_id: str | None,
        category_id: int | None,
        notes: str | None,
        tags: list[str],
    ) -> Video:
        source = Path(file_path)
        if not source.is_file():
            raise FileOperationError(f"File not found: {file_path}")

        if category_id is not None and self.categories.get(category_id) is None:
            raise NotFoundError("Category", category_id)

        resolved_external_id = external_id or f"local-{source.stem}-{int(_utcnow().timestamp())}"

        existing = catalog.find_video(self.db, platform, resolved_external_id)
        if existing is not None:
            raise ValidationError(f"A video with external_id {resolved_external_id!r} already exists")

        video = catalog.create_video(
            self.db,
            catalog.VideoMetadataIn(
                platform=platform,
                external_id=resolved_external_id,
                channel_name=channel_name,
                title=title,
                original_url=f"file://{source.resolve()}",
            ),
        )

        imported_at = _utcnow()
        metadata = VideoMetadata(
            platform=platform,
            video_id=resolved_external_id,
            channel_name=channel_name,
            title=title,
            original_url=video.original_url,
            thumbnail_url=None,
            views=None,
            likes=None,
            duration_sec=None,
            upload_date=None,
            tags=tags,
        )
        try:
            final_path = organize_imported_file(source, self.library_dir, metadata, imported_at)
        except OSError as exc:
            raise FileOperationError(f"Could not import file {file_path}: {exc}") from exc

        video.video_path = str(final_path)
        video.filesize_bytes = final_path.stat().st_size
        video.is_downloaded = True
        video.downloaded_at = imported_at
        video.category_id = category_id
        video.notes = notes

        self.videos.save(video)
        if tags:
            self.add_tags(video.id, tags)

        return video


class CategoryService:
    def __init__(self, db: Session):
        self.categories = CategoryRepository(db)

    def list(self):
        return self.categories.list()


class EmotionService:
    def __init__(self, db: Session):
        self.emotions = EmotionRepository(db)

    def list(self):
        return self.emotions.list()


class TagService:
    def __init__(self, db: Session):
        self.tags = TagRepository(db)

    def list(self, query: str | None = None):
        return self.tags.list(query)

    def create(self, name: str):
        name = name.strip()
        if not name:
            raise ValidationError("Tag name cannot be empty")
        if self.tags.get_by_name(name) is not None:
            raise ValidationError(f"Tag {name!r} already exists")
        return self.tags.create(name)

    def rename(self, tag_id: int, new_name: str):
        tag = self.tags.get(tag_id)
        if tag is None:
            raise NotFoundError("Tag", tag_id)
        new_name = new_name.strip()
        if not new_name:
            raise ValidationError("Tag name cannot be empty")
        conflict = self.tags.get_by_name(new_name)
        if conflict is not None and conflict.id != tag_id:
            raise ValidationError(f"Tag {new_name!r} already exists")
        return self.tags.rename(tag, new_name)

    def delete(self, tag_id: int) -> None:
        tag = self.tags.get(tag_id)
        if tag is None:
            raise NotFoundError("Tag", tag_id)
        self.tags.delete(tag)

    def merge(self, source_tag_id: int, target_tag_id: int):
        if source_tag_id == target_tag_id:
            raise ValidationError("Cannot merge a tag into itself")
        source = self.tags.get(source_tag_id)
        if source is None:
            raise NotFoundError("Tag", source_tag_id)
        target = self.tags.get(target_tag_id)
        if target is None:
            raise NotFoundError("Tag", target_tag_id)
        return self.tags.merge(source, target)
