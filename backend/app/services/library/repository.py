from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.channel import Channel
from app.models.emotion import Emotion
from app.models.favorite import Favorite
from app.models.platform import Platform
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_tag import VideoTag

DURATION_BUCKETS = {
    "<30": (None, 30),
    "30-60": (30, 60),
    "1-3min": (60, 180),
    ">3min": (180, None),
}

RESOLUTION_BUCKETS = {
    "720": "720",
    "1080": "1080",
    "4k": "2160",
}

SORT_OPTIONS = {
    "newest": (Video.created_at, True),
    "oldest": (Video.created_at, False),
    "title": (Video.title, False),
    "duration": (Video.duration_sec, False),
    "download_date": (Video.downloaded_at, True),
    "file_size": (Video.filesize_bytes, True),
    "channel": (Channel.name, False),
    "platform": (Platform.name, False),
}


@dataclass
class VideoFilters:
    search: str | None = None
    platform: str | None = None
    status: str | None = None
    category_id: int | None = None
    emotion_id: int | None = None
    tag: str | None = None
    favorite: bool | None = None
    duration: str | None = None
    resolution: str | None = None
    sort: str = "newest"
    page: int = 1
    page_size: int = 50


class VideoRepository:
    """Query/persistence only -- no business rules. Business rules (status
    transitions, tag get-or-create, favorite semantics) live in the Service
    layer.
    """

    def __init__(self, db: Session):
        self.db = db

    def get(self, video_id: int) -> Video | None:
        return self.db.get(Video, video_id)

    def list(self, filters: VideoFilters) -> tuple[list[Video], int]:
        query = self.db.query(Video).join(Channel, Video.channel_id == Channel.id).join(
            Platform, Video.platform_id == Platform.id
        )

        if filters.search:
            like = f"%{filters.search}%"
            query = query.outerjoin(VideoTag, VideoTag.video_id == Video.id).outerjoin(
                Tag, Tag.id == VideoTag.tag_id
            )
            query = query.filter(
                or_(Video.title.ilike(like), Channel.name.ilike(like), Tag.name.ilike(like))
            ).distinct()

        if filters.platform:
            query = query.filter(Platform.name == filters.platform)

        if filters.status:
            query = query.filter(Video.status == filters.status)

        if filters.category_id is not None:
            query = query.filter(Video.category_id == filters.category_id)

        if filters.emotion_id is not None:
            query = query.filter(Video.emotion_id == filters.emotion_id)

        if filters.tag:
            query = query.filter(
                Video.id.in_(
                    self.db.query(VideoTag.video_id).join(Tag, Tag.id == VideoTag.tag_id).filter(
                        Tag.name == filters.tag
                    )
                )
            )

        if filters.favorite is not None:
            favorited_ids = self.db.query(Favorite.video_id)
            query = query.filter(Video.id.in_(favorited_ids)) if filters.favorite else query.filter(
                Video.id.notin_(favorited_ids)
            )

        if filters.duration and filters.duration in DURATION_BUCKETS:
            low, high = DURATION_BUCKETS[filters.duration]
            if low is not None:
                query = query.filter(Video.duration_sec >= low)
            if high is not None:
                query = query.filter(Video.duration_sec < high)

        if filters.resolution and filters.resolution in RESOLUTION_BUCKETS:
            query = query.filter(Video.resolution.ilike(f"%{RESOLUTION_BUCKETS[filters.resolution]}%"))

        total = query.count()

        sort_column, descending = SORT_OPTIONS.get(filters.sort, SORT_OPTIONS["newest"])
        query = query.order_by(sort_column.desc() if descending else sort_column.asc())

        page = max(filters.page, 1)
        page_size = max(1, min(filters.page_size, 200))
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return items, total

    def save(self, video: Video) -> Video:
        self.db.commit()
        self.db.refresh(video)
        return video

    def delete(self, video: Video) -> None:
        self.db.query(VideoTag).filter(VideoTag.video_id == video.id).delete(synchronize_session=False)
        self.db.query(Favorite).filter(Favorite.video_id == video.id).delete(synchronize_session=False)
        # video.favorite/tags were joined-loaded and are now stale in the identity
        # map after the bulk deletes above; without expiring, SQLAlchemy's unit of
        # work tries to "blank out" the (already gone) child rows when deleting
        # video, which fails because Favorite.video_id is both PK and FK.
        self.db.expire(video)
        self.db.delete(video)
        self.db.commit()

    def set_favorite(self, video_id: int, favorite: bool) -> None:
        existing = self.db.get(Favorite, video_id)
        if favorite and existing is None:
            self.db.add(Favorite(video_id=video_id))
        elif not favorite and existing is not None:
            self.db.delete(existing)
        self.db.commit()


class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[Category]:
        return self.db.query(Category).order_by(Category.name).all()

    def get(self, category_id: int) -> Category | None:
        return self.db.get(Category, category_id)


class EmotionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[Emotion]:
        return self.db.query(Emotion).order_by(Emotion.name).all()

    def get(self, emotion_id: int) -> Emotion | None:
        return self.db.get(Emotion, emotion_id)


class TagRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, query: str | None = None) -> list[Tag]:
        q = self.db.query(Tag)
        if query:
            q = q.filter(Tag.name.ilike(f"%{query}%"))
        return q.order_by(Tag.name).all()

    def get(self, tag_id: int) -> Tag | None:
        return self.db.get(Tag, tag_id)

    def get_by_name(self, name: str) -> Tag | None:
        return self.db.query(Tag).filter_by(name=name).one_or_none()

    def create(self, name: str) -> Tag:
        tag = Tag(name=name)
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def rename(self, tag: Tag, new_name: str) -> Tag:
        tag.name = new_name
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def delete(self, tag: Tag) -> None:
        self.db.query(VideoTag).filter(VideoTag.tag_id == tag.id).delete()
        self.db.delete(tag)
        self.db.commit()

    def merge(self, source: Tag, target: Tag) -> Tag:
        videos_with_target = {
            row[0] for row in self.db.query(VideoTag.video_id).filter(VideoTag.tag_id == target.id)
        }
        source_links = self.db.query(VideoTag).filter(VideoTag.tag_id == source.id).all()
        for link in source_links:
            if link.video_id in videos_with_target:
                self.db.delete(link)
            else:
                link.tag_id = target.id
        self.db.delete(source)
        self.db.commit()
        self.db.refresh(target)
        return target

    def add_to_video(self, video_id: int, tag_id: int) -> None:
        exists = self.db.query(VideoTag).filter_by(video_id=video_id, tag_id=tag_id).one_or_none()
        if exists is None:
            self.db.add(VideoTag(video_id=video_id, tag_id=tag_id))
            self.db.commit()

    def remove_from_video(self, video_id: int, tag_id: int) -> None:
        self.db.query(VideoTag).filter_by(video_id=video_id, tag_id=tag_id).delete()
        self.db.commit()
