from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.platform import Platform
from app.models.playlist import Playlist, PlaylistVideo
from app.models.video import Video


@dataclass
class PlaylistMetadataIn:
    external_id: str
    title: str


@dataclass
class VideoMetadataIn:
    platform: str
    external_id: str
    channel_name: str
    title: str
    original_url: str
    thumbnail_url: str | None = None
    views: int | None = None
    likes: int | None = None
    duration_sec: int | None = None
    upload_date: str | None = None


def get_or_create_platform(db: Session, name: str) -> Platform:
    platform = db.query(Platform).filter_by(name=name).one_or_none()
    if platform is not None:
        return platform
    platform = Platform(name=name)
    db.add(platform)
    db.flush()
    return platform


def get_or_create_channel(db: Session, platform_name: str, name: str) -> Channel:
    platform = get_or_create_platform(db, platform_name)
    channel = db.query(Channel).filter_by(platform_id=platform.id, name=name).one_or_none()
    if channel is not None:
        return channel
    channel = Channel(platform_id=platform.id, name=name)
    db.add(channel)
    db.flush()
    return channel


def find_video(db: Session, platform_name: str, external_id: str) -> Video | None:
    platform = db.query(Platform).filter_by(name=platform_name).one_or_none()
    if platform is None:
        return None
    return db.query(Video).filter_by(platform_id=platform.id, external_id=external_id).one_or_none()


def create_video(db: Session, metadata: VideoMetadataIn) -> Video:
    channel = get_or_create_channel(db, metadata.platform, metadata.channel_name)
    video = Video(
        platform_id=channel.platform_id,
        external_id=metadata.external_id,
        channel_id=channel.id,
        title=metadata.title,
        original_url=metadata.original_url,
        thumbnail_url=metadata.thumbnail_url,
        views=metadata.views,
        likes=metadata.likes,
        duration_sec=metadata.duration_sec,
        upload_date=metadata.upload_date,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def link_playlist(db: Session, video: Video, platform: str, playlist_meta: PlaylistMetadataIn) -> None:
    playlist = (
        db.query(Playlist).filter_by(platform=platform, external_id=playlist_meta.external_id).one_or_none()
    )
    if playlist is None:
        playlist = Playlist(
            platform=platform,
            external_id=playlist_meta.external_id,
            title=playlist_meta.title,
            channel_id=video.channel_id,
        )
        db.add(playlist)
        db.flush()

    already_linked = (
        db.query(PlaylistVideo).filter_by(playlist_id=playlist.id, video_id=video.id).one_or_none()
    )
    if already_linked is None:
        db.add(PlaylistVideo(playlist_id=playlist.id, video_id=video.id))
    db.commit()
