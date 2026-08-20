"""Shared generation-history log for every app/modules/ai/* generator.
One table, not one per sub-feature -- story/hook/caption are sub-packages
of the same `ai` module (not separate modules per app/modules/README.md),
so sharing this is exactly what that isolation rule allows.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base

AI_GENERATION_KINDS = ("story", "hook", "caption", "quality_score")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIGenerationHistory(Base):
    """job_id is a loose reference (no FK) -- it points at story_job,
    hook_job, or caption_job depending on `kind`, and a single column can't
    carry a real FK to three different tables. Task 05 adds a 4th kind,
    "quality_score" -- job_id there points at story_version.id (the score
    is per-*version*, not per-job, since a StoryJob has multiple versions
    with independent quality).
    """

    __tablename__ = "ai_generation_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), nullable=False)

    provider: Mapped[str] = mapped_column(String, nullable=False, default="anthropic")
    model: Mapped[str] = mapped_column(String, nullable=False)

    prompt_system: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_user: Mapped[str | None] = mapped_column(String, nullable=True)
    response_raw: Mapped[str | None] = mapped_column(String, nullable=True)

    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


def record(
    db: Session,
    *,
    kind: str,
    job_id: int | None,
    video_id: int,
    model: str,
    prompt_system: str | None,
    prompt_user: str | None,
    response_raw: str | None,
    latency_ms: int,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_message: str | None = None,
    provider: str = "anthropic",
) -> None:
    # Deliberately no commit() here -- callers commit this alongside their
    # own job/version rows in the same transaction, so a history row is
    # never persisted without (or ahead of) its corresponding job.
    db.add(
        AIGenerationHistory(
            kind=kind,
            job_id=job_id,
            video_id=video_id,
            provider=provider,
            model=model,
            prompt_system=prompt_system,
            prompt_user=prompt_user,
            response_raw=response_raw,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error_message=error_message,
        )
    )
