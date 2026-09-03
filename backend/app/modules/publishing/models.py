"""Publishing tables: YouTubeChannel (a connected channel + its OAuth
tokens) and YouTubeUploadJob (one upload attempt of one project to one
channel).

Own tables, no FK into any other module's tables -- `YouTubeUploadJob`'s
`project_id` / `render_job_id` are bare ints (the same "bare FK column, no
relationship()" shape app.modules.competitor_intelligence.models and
app.modules.news.models use). Status vocabularies are validated in
schemas.py (Pydantic), never a DB CHECK constraint -- same pattern as
every other status field in this codebase.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

UPLOAD_JOB_STATUSES = ("pending", "uploading", "completed", "failed", "interrupted")
UPLOAD_JOB_ACTIVE_STATUSES = ("pending", "uploading")

# What privacy we ASK YouTube for. An un-audited OAuth project has YouTube
# force every result to "private" anyway (see module docstring) -- the
# requested value still matters once the user's OAuth app is verified.
YOUTUBE_PRIVACY_STATUSES = ("private", "unlisted", "public")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class YouTubeChannel(Base):
    """One connected YouTube channel. `refresh_token` is the long-lived
    credential; `access_token`/`access_token_expires_at` are the short-lived
    working token refreshed on demand before an upload.
    """

    __tablename__ = "youtube_channel"

    id: Mapped[int] = mapped_column(primary_key=True)
    # YouTube's own channel id (UC...), unique -- reconnecting the same
    # channel updates the existing row rather than duplicating it.
    channel_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)

    refresh_token: Mapped[str] = mapped_column(String, nullable=False)
    access_token: Mapped[str | None] = mapped_column(String, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    uploads: Mapped[list["YouTubeUploadJob"]] = relationship(
        "YouTubeUploadJob", back_populates="channel", cascade="all, delete-orphan"
    )


class YouTubeUploadJob(Base):
    """One upload of one produced video to one channel. Idempotency is by
    (channel_id, project_id) at the composition-root layer -- a project
    already uploaded to a channel is not re-uploaded unless the user
    explicitly retries.
    """

    __tablename__ = "youtube_upload_job"
    __table_args__ = (
        Index("ix_youtube_upload_job_channel", "channel_pk"),
        Index("ix_youtube_upload_job_project", "project_id"),
        Index("ix_youtube_upload_job_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_pk: Mapped[int] = mapped_column(ForeignKey("youtube_channel.id"), nullable=False)

    # Bare ints -- this module must never import app.modules.beat /
    # app.modules.video_composer.
    project_id: Mapped[int] = mapped_column(nullable=False)
    render_job_id: Mapped[int | None] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    requested_privacy: Mapped[str] = mapped_column(String, nullable=False, default="private")

    # A snapshot of what was sent, for the UI + so a retry can reuse it.
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_path: Mapped[str | None] = mapped_column(String, nullable=True)

    youtube_video_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    channel: Mapped["YouTubeChannel"] = relationship("YouTubeChannel", back_populates="uploads")

    @property
    def watch_url(self) -> str | None:
        return f"https://www.youtube.com/watch?v={self.youtube_video_id}" if self.youtube_video_id else None
