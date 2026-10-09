"""Vox Documentary Factory tables (feature 163). Phase 1 owns only the
project row and its approval history; later phases add research / script /
scene / asset tables in their own migrations."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentaryProject(Base):
    __tablename__ = "documentary_project"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="vi")
    state: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    # Set only while state == "failed": where to resume to.
    failed_from_state: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # One monotonically increasing counter per approvable artifact. An
    # approval records the counter it approved; a bump makes it stale.
    research_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    script_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storyboard_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    narration_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    render_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class DocumentaryApproval(Base):
    """Append-only approval history. The *latest* row per (project, gate)
    decides the current status; nothing is ever updated or deleted."""

    __tablename__ = "documentary_approval"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), nullable=False, index=True)
    gate: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)  # approved | rejected | revoked
    artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class DocumentarySource(Base):
    """A manually entered research source. Nothing here is ever fetched or
    generated -- every field is what the user typed."""

    __tablename__ = "documentary_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    accessed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class DocumentaryClaim(Base):
    __tablename__ = "documentary_claim"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="unverified")
    uncertainty_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class DocumentaryClaimSource(Base):
    __tablename__ = "documentary_claim_source"
    __table_args__ = (UniqueConstraint("claim_id", "source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("documentary_claim.id"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("documentary_source.id"), nullable=False, index=True)


class DocumentaryScript(Base):
    """One saved version of the outline/script. Append-only: an edit is a new
    row whose `version` equals the project's script_version after the bump,
    which is exactly the number an approval records."""

    __tablename__ = "documentary_script"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)  # manual | mock | llm
    # Explicit-schema JSON (see schemas.OutlineItem / ScriptSection), validated on write.
    outline: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
