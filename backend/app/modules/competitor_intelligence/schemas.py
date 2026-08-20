from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TikTokAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    open_id: str
    username: str | None
    display_name: str | None
    avatar_url: str | None
    follower_count: int | None
    following_count: int | None
    likes_count: int | None
    video_count: int | None
    status: str
    scope: str
    connected_at: datetime
    last_synced_at: datetime | None


class TikTokVideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tiktok_video_id: str
    title: str | None
    video_description: str | None
    duration_sec: int | None
    cover_image_url: str | None
    share_url: str | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    share_count: int | None
    posted_at: datetime | None
    synced_at: datetime


class OAuthAuthorizeUrlOut(BaseModel):
    authorize_url: str


class SyncTriggerOut(BaseModel):
    started: bool
    already_syncing: bool


class CompetitorVideoCreateIn(BaseModel):
    source_url: str
    competitor_handle: str | None = None
    title_caption: str | None = None
    duration_sec: float | None = None
    notes: str | None = None


class CompetitorVideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_url: str
    competitor_handle: str | None
    title_caption: str | None
    thumbnail_url: str | None
    author_name: str | None
    duration_sec: float | None
    notes: str | None
    added_at: datetime

    emotional_pattern: str | None
    hook_structure: str | None
    conflict_type: str | None
    character_type: str | None
    ending_style: str | None
    estimated_format: str | None
    reasoning: str | None
    analyzed_at: datetime | None
