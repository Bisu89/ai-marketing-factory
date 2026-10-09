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


class DocumentaryAsset(Base):
    """Project asset registry. `origin` records where the file came from and
    `license`/`attribution` are mandatory before an archival asset can be
    approved -- a publicly visible image is never assumed to be reusable."""

    __tablename__ = "documentary_asset"
    __table_args__ = (UniqueConstraint("project_id", "content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False, default="image")
    origin: Mapped[str] = mapped_column(String, nullable=False)  # imported | archival | ai_manual
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    license: Mapped[str | None] = mapped_column(String, nullable=True)
    attribution: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    approval_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class DocumentaryScene(Base):
    __tablename__ = "documentary_scene"
    __table_args__ = (UniqueConstraint("project_id", "scene_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), nullable=False, index=True)
    # Stable across re-plans for unchanged narration; never reused after deletion.
    scene_key: Mapped[str] = mapped_column(String, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_kind: Mapped[str] = mapped_column(String, nullable=False)
    narration_text: Mapped[str] = mapped_column(Text, nullable=False)
    narration_hash: Mapped[str] = mapped_column(String, nullable=False)
    claim_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    visual_objective: Mapped[str] = mapped_column(Text, nullable=False)
    visual_preset: Mapped[str] = mapped_column(String, nullable=False)
    asset_strategy: Mapped[str] = mapped_column(String, nullable=False)  # programmatic | image
    image_group: Mapped[str | None] = mapped_column(String, nullable=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("documentary_asset.id"), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    # input_hash at the moment the current asset was assigned; a later mismatch means the image is stale.
    assigned_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    on_screen_text: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    motion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sfx_cues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expected_duration: Mapped[float] = mapped_column(Float, nullable=False)
    actual_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    render_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    user_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class DocumentaryProjectCounter(Base):
    """Monotonic scene-key counter per project, so a deleted scene's key is
    never handed out again."""

    __tablename__ = "documentary_scene_counter"

    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), primary_key=True)
    next_scene: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    next_segment: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class DocumentaryNarrationSegment(Base):
    """One TTS request's worth of narration (a few scenes, roughly a
    paragraph). `cache_key` records exactly which text+voice produced the
    audio on disk, so an unchanged segment is never re-synthesised."""

    __tablename__ = "documentary_narration_segment"
    __table_args__ = (UniqueConstraint("project_id", "segment_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), nullable=False, index=True)
    segment_key: Mapped[str] = mapped_column(String, nullable=False)  # N001...
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String, nullable=False)
    scene_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cache_key: Mapped[str | None] = mapped_column(String, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    voice: Mapped[str | None] = mapped_column(String, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)  # None = unknown, never a guessed 0
    # Word timestamps handed back by the TTS provider itself (None when it has none).
    word_stamps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending | ready | failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_key: Mapped[str | None] = mapped_column(String, nullable=True)  # cache key the attempts count belongs to
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    master_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    master_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class DocumentaryUsage(Base):
    """Append-only ledger of provider spend/usage, so regenerating a segment
    never erases what the earlier attempt cost."""

    __tablename__ = "documentary_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("documentary_project.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # tts | alignment | ...
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    ref: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. segment key
    chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
