"""Viral Source Radar tables.

Own tables, no FK into any other module. `DiscoveryResult.saved_video_id`
is a bare int (the "bare cross-module ref, no relationship()" shape the
news / content_batch modules already use) -- set once the user saves a
result into the core Library `video` table.

Status vocabularies live in Pydantic (schemas.py), never a DB CHECK
constraint -- same as every other status field in this codebase.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiscoverySearch(Base):
    """One run of the search box. `engine_statuses_json` / `expanded_queries_json`
    are small JSON blobs (list/dict) -- read-only provenance for the UI, not
    queried, so no separate table."""

    __tablename__ = "discovery_search"
    __table_args__ = (Index("ix_discovery_search_created", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    normalized_query: Mapped[str] = mapped_column(String, nullable=False)
    expanded_queries_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine_statuses_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    results: Mapped[list[DiscoveryResult]] = relationship(
        "DiscoveryResult", back_populates="search", cascade="all, delete-orphan"
    )


class DiscoveryResult(Base):
    """One normalized, scored candidate persisted from a search (so
    GET /discover/{id} can replay it and a Save can reference a stable row).
    """

    __tablename__ = "discovery_result"
    __table_args__ = (
        Index("ix_discovery_result_search", "search_id"),
        Index("ix_discovery_result_platform", "platform"),
        Index("ix_discovery_result_viral", "viral_score"),
        Index("ix_discovery_result_saved", "saved_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("discovery_search.id"), nullable=False)

    platform: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)

    creator_name: Mapped[str | None] = mapped_column(String, nullable=True)
    creator_url: Mapped[str | None] = mapped_column(String, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)

    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    content_tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    also_on_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recency_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    short_form_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    content_signal_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    viral_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    rights_status: Mapped[str] = mapped_column(String, default="UNKNOWN", nullable=False)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_capability: Mapped[str] = mapped_column(
        String, default="PERMISSION_REQUIRED", nullable=False
    )

    # Save system (brief section 19). `saved_at` is the "is this shortlisted"
    # flag; `collection` groups saved sources. `saved_video_id` is a bare
    # cross-module ref reserved for a Phase 3 "promote to Library" action.
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    saved_video_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    collection: Mapped[str | None] = mapped_column(String, nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    search: Mapped[DiscoverySearch] = relationship("DiscoverySearch", back_populates="results")
