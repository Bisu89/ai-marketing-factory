"""Competitor Content Analyzer (Task 11 -- see
docs/features/76-competitor-content-analyzer.md). Own table(s), no FK into
core/other modules per app/modules/README.md.

Two, deliberately separate, concerns:

- TikTokAccountLink/TikTokVideo -- the user's OWN TikTok account, connected
  via real OAuth (TikTok Login Kit + Display API). Real tokens, real
  public metrics.
- CompetitorVideo -- a competitor's video the user manually submitted for
  analysis. There is no official TikTok API a commercial app can use to
  pull an arbitrary competitor's videos/metrics (see this feature's own
  capability-audit doc) -- so this table only ever holds what the user
  typed in after viewing a public video in their own browser, optionally
  enriched with oEmbed's title/thumbnail/author (also public, also no
  auth). No engagement/duration/frequency numbers are stored here unless
  the user typed them in themselves -- never fabricated.

Tokens are stored in plaintext columns, same posture as every other
secret in this desktop-local, single-user app (see app/core/config.py's
own anthropic_api_key/openai_api_key, which live in a plaintext .env) --
not a new, weaker security stance, just the existing one applied here too.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TIKTOK_ACCOUNT_STATUSES = ("connected", "disconnected", "token_expired")

# The task's own required output shape for a competitor video's abstract
# analysis -- see module docstring/README for why these are plain nullable
# columns on CompetitorVideo rather than a separate table (mirrors
# StoryVersion's own quality_score columns, Task 05: no product need to
# keep more than the latest analysis per video).
COMPETITOR_ANALYSIS_FIELDS = (
    "emotional_pattern",
    "hook_structure",
    "conflict_type",
    "character_type",
    "ending_style",
    "estimated_format",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TikTokAccountLink(Base):
    """One connected TikTok account (this app's own, via OAuth). Multiple
    rows are allowed over time (disconnect + reconnect a different
    account) -- `status` distinguishes the currently-active one; the
    module's own service.get_active_account() is the single place that
    resolves "the" connected account.
    """

    __tablename__ = "tiktok_account_link"

    id: Mapped[int] = mapped_column(primary_key=True)
    open_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Profile stats (user.info.stats scope) -- refreshed on every sync,
    # never a running local count (see TikTokVideo -- video-level metrics
    # are separate and also always overwritten from the live API, never
    # incremented locally).
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    following_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    access_token: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[str] = mapped_column(String, nullable=False)
    access_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False, default="")

    status: Mapped[str] = mapped_column(String, nullable=False, default="connected")
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    videos: Mapped[list["TikTokVideo"]] = relationship("TikTokVideo", back_populates="account")


class TikTokVideo(Base):
    """One of the connected account's own public videos, synced via the
    Display API's video.list scope. Every metric column is overwritten in
    full on each sync (see service.upsert_videos) -- this is a snapshot of
    "as of the last sync," never a locally-accumulated counter.
    """

    __tablename__ = "tiktok_video"
    __table_args__ = ()

    id: Mapped[int] = mapped_column(primary_key=True)
    account_link_id: Mapped[int] = mapped_column(ForeignKey("tiktok_account_link.id"), nullable=False, index=True)
    tiktok_video_id: Mapped[str] = mapped_column(String, nullable=False)

    title: Mapped[str | None] = mapped_column(String, nullable=True)
    video_description: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    share_url: Mapped[str | None] = mapped_column(String, nullable=True)

    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    account: Mapped[TikTokAccountLink] = relationship("TikTokAccountLink", back_populates="videos")


class CompetitorVideo(Base):
    """A competitor's public video, manually submitted for analysis --
    see module docstring for why this is never auto-fetched in bulk.
    `analyzed_at`/`analysis_*` stay NULL until POST
    /competitor-videos/{id}/analyze actually runs (composition root --
    see app/api/v1/endpoints/competitor_analysis.py).
    """

    __tablename__ = "competitor_video"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    competitor_handle: Mapped[str | None] = mapped_column(String, nullable=True)
    # User-entered (what they read publicly) and/or oEmbed-filled title/caption.
    title_caption: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)
    author_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Only ever set if the user typed it in -- oEmbed does not return
    # duration, and this app never estimates or guesses it.
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # -- Abstract pattern analysis (never the original script/caption text) --
    emotional_pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    hook_structure: Mapped[str | None] = mapped_column(String, nullable=True)
    conflict_type: Mapped[str | None] = mapped_column(String, nullable=True)
    character_type: Mapped[str | None] = mapped_column(String, nullable=True)
    ending_style: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_format: Mapped[str | None] = mapped_column(String, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Own provider/model/token columns rather than a row in
    # app.modules.ai.history.AIGenerationHistory -- that table's video_id
    # is a NOT NULL FK to the core Library `video` table, which a
    # competitor's video (never downloaded, never in this app's Library)
    # has no way to satisfy. Task 10's AI Cost Tracking therefore does not
    # cover this feature's AI spend -- a real, disclosed gap, not silently
    # folded into a table it doesn't fit.
    analysis_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    analysis_model: Mapped[str | None] = mapped_column(String, nullable=True)
    analysis_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
