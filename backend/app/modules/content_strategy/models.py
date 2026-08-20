"""Content Strategy planning layer: Pillar -> Format -> Idea.

Its own tables, no FK into any other app/modules/* table (per
app/modules/README.md, a module may never import another module).
`ContentIdea.target_emotion_id` is the one module -> core FK, mirroring
`app.modules.scene_cutter.models.SceneCutJob.video_id` (a bare FK column,
deliberately with no `relationship()` back-reference -- see that file):
it reuses the existing seeded `emotion` catalog (app/models/emotion.py)
instead of duplicating its values here, per this task's explicit "reuse
existing database entities where appropriate" instruction.

Pillar/Format names are deliberately NOT a hardcoded Python enum/tuple --
they are plain, user-manageable rows (a starter set of Pillars is seeded by
seed.py, same "seeded starter set, not a hardcoded constraint" shape as the
existing core `category`/`emotion` lookup tables), read by whatever future
business logic needs them rather than baked into it.

Does NOT create a new Story table. Note for future readers: the brief this
module was built from says `story_job`/`story_version` remain the source of
truth for generated stories -- those tables were in fact removed from this
codebase just before this task (see
docs/features/63-remove-ai-content-and-insights.md). ContentIdea does not
reference story_job at all and does not duplicate generated-story storage,
so nothing here depends on whether/how that table comes back; see that doc
and docs/features/64-content-strategy-database.md for the full note.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Planning status of a ContentIdea as it moves toward (or away from) being
# turned into an actual story: draft (just captured) -> approved (worth
# producing) -> used (a story was generated from it) or rejected (won't be
# used). Validated in schemas.py (Pydantic), not a DB CHECK constraint --
# same pattern as every other status field in this codebase (e.g.
# app.models.publish_log.PUBLISH_LOG_STATUSES).
CONTENT_IDEA_STATUSES = ("draft", "approved", "rejected", "used")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentPillar(Base):
    """A broad, recurring content theme (e.g. "Love", "Family", "Female
    Self-worth") that a ContentFormat, and transitively a ContentIdea,
    belongs to.
    """

    __tablename__ = "content_pillar"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    formats: Mapped[list["ContentFormat"]] = relationship(
        "ContentFormat", back_populates="pillar", order_by="ContentFormat.name"
    )


class ContentFormat(Base):
    """A recurring narrative shape within a Pillar (e.g. "Betrayal", "Mother
    Story", "Unexpected Twist"). Belongs to exactly one Pillar; the same
    format name may be reused under a different Pillar (e.g. a "Betrayal"
    format could exist under both "Love" and "Marriage" as two distinct
    rows), so uniqueness is scoped to (pillar_id, name), not name alone.
    """

    __tablename__ = "content_format"
    __table_args__ = (
        UniqueConstraint("pillar_id", "name", name="uq_content_format_pillar_name"),
        Index("ix_content_format_pillar", "pillar_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pillar_id: Mapped[int] = mapped_column(ForeignKey("content_pillar.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    pillar: Mapped["ContentPillar"] = relationship("ContentPillar", back_populates="formats")


class ContentIdea(Base):
    """One planning-stage content idea -- the input a future AI generation
    step (Story, per the long-term pipeline) will read from, never a
    duplicate of story_job/story_version's own generated-output storage.
    Belongs to exactly one Pillar and one Format (Format's own pillar_id is
    not assumed to match `pillar_id` at the DB level -- SQLite has no
    trivial way to enforce "child FK belongs to this same parent" without
    triggers; the service layer that will be built on top of this in a
    later task is the right place for that check).
    """

    __tablename__ = "content_idea"
    __table_args__ = (
        Index("ix_content_idea_pillar", "pillar_id"),
        Index("ix_content_idea_format", "format_id"),
        Index("ix_content_idea_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pillar_id: Mapped[int] = mapped_column(ForeignKey("content_pillar.id"), nullable=False)
    format_id: Mapped[int] = mapped_column(ForeignKey("content_format.id"), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    premise: Mapped[str | None] = mapped_column(String, nullable=True)

    # Reuses the existing seeded `emotion` catalog (Vui/Cảm động/...) rather
    # than duplicating its values here -- see module docstring. No
    # relationship() back-reference, matching
    # app.modules.scene_cutter.models.SceneCutJob.video_id.
    target_emotion_id: Mapped[int | None] = mapped_column(ForeignKey("emotion.id"), nullable=True)

    # Free-form for now (e.g. "affiliate: haircare", "none") -- the later
    # Affiliate task (explicitly out of scope here) is what will give this
    # real structure; forcing a shape now would be guessing.
    commercial_intent: Mapped[str | None] = mapped_column(String, nullable=True)

    # Set by the future "AI Quality Score" pipeline stage (out of scope
    # here); None means "not yet scored".
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    pillar: Mapped["ContentPillar"] = relationship("ContentPillar")
    format: Mapped["ContentFormat"] = relationship("ContentFormat")
