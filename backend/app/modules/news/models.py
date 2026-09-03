"""News Ingestion tables: NewsSource (an RSS/Atom feed the user follows) and
NewsItem (one deduplicated article pulled from a source).

Own tables, no FK into any other module's tables -- `NewsItem.project_id`/
`batch_id` are bare ints (the same "bare FK column, no relationship()"
shape app.modules.content_batch.models uses for its own cross-module refs),
set by the composition root once an item is turned into a real Factory
Project. Status vocabularies are validated in schemas.py (Pydantic), never
a DB CHECK constraint -- same pattern as every other status field in this
codebase.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# A NewsItem's lifecycle from "just pulled from a feed" to "a video was made
# from it":
#   new       -- freshly ingested, nothing done with it yet
#   drafted   -- an AI narration script has been generated (item.script_text)
#   queued    -- a Factory Project + Batch item was created from it
#   used      -- that project's render finished
#   dismissed -- the user hid it (never turned into a video)
NEWS_ITEM_STATUSES = ("new", "drafted", "queued", "used", "dismissed")
NEWS_ITEM_ACTIVE_STATUSES = ("new", "drafted")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NewsSource(Base):
    """One RSS/Atom feed. `category` is a free-text label the user picks
    (e.g. "Thế giới", "Kinh tế") -- surfaced on the item list for grouping,
    not a FK into any catalog. `language` is the language its articles are
    written in, defaulting the drafted script's output language unless the
    chosen Template overrides it.
    """

    __tablename__ = "news_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    feed_url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False, default="vi")

    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    items: Mapped[list["NewsItem"]] = relationship(
        "NewsItem", back_populates="source", cascade="all, delete-orphan"
    )


class NewsItem(Base):
    """One article from a feed. Deduplicated per source on `guid` (the feed
    entry's own id, or its link when it has none) AND, across sources, on
    `fingerprint` (a normalized-title hash) so the same wire story syndicated
    to two feeds is not turned into two videos.
    """

    __tablename__ = "news_item"
    __table_args__ = (
        UniqueConstraint("source_id", "guid", name="uq_news_item_source_guid"),
        Index("ix_news_item_source", "source_id"),
        Index("ix_news_item_status", "status"),
        Index("ix_news_item_fingerprint", "fingerprint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("news_source.id"), nullable=False)

    guid: Mapped[str] = mapped_column(String, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="new")

    # The AI-drafted narration script (set by the news_pipeline composition
    # root's draft-script action); None until then.
    script_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Bare ints, no FK/relationship -- this module must never import
    # app.modules.beat / app.modules.batch. Set once the item is turned into
    # a Factory Project.
    project_id: Mapped[int | None] = mapped_column(nullable=True)
    batch_id: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    source: Mapped["NewsSource"] = relationship("NewsSource", back_populates="items")
