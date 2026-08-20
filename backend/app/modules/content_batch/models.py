"""Batch content generation (Task 06): many ContentIdeas -> many
Story-generation-and-scoring attempts, run in the background so a batch
of 20-30 real AI calls never blocks an HTTP request. Mirrors
app.modules.batch's own module docstring/shape exactly -- own table(s),
never a real FK into app.modules.content_strategy or app.modules.ai.story
(per app/modules/README.md, a module may never import another module).
`idea_id`/`story_job_id`/`story_version_id` below are bare, unconstrained
ints, the same "cross-module reference without a real FK" convention
already used throughout this codebase (BatchItem.project_id,
PublishLog.ai_story_job_id, AIGenerationHistory.job_id, etc). The actual
cross-module orchestration (load the ContentIdea, call StoryService,
call StoryQualityService) lives in the composition root --
app/api/v1/endpoints/content_batch_generate.py -- the only place allowed
to import content_batch, content_strategy, and ai.story together.

`video_id` is a real FK, unlike the above -- `video` is core, and
module -> core FK is the one allowed link direction (see
app.modules.scene_cutter.models.SceneCutJob.video_id). Every item in a
ContentBatch shares the same `video_id`: StoryJob.video_id is NOT NULL
(Story has always been "narration options for one already-downloaded
Video," never redesigned for a video-less planning idea), and a batch of
fresh ContentIdeas has no video of its own yet, so this batch feature
works within that existing constraint by generating every item's Story
under one caller-chosen Video, rather than requiring 20 pre-downloaded
videos before a batch can even start.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

CONTENT_BATCH_STATUSES = ("DRAFT", "PROCESSING", "COMPLETED", "PARTIAL_FAILURE", "FAILED", "CANCELLED")

# The task's own required vocabulary (pending/generating/completed/scored/
# approved/rejected/failed) plus CANCELLED -- needed because "cancel if
# existing architecture supports cancellation" is itself a requirement,
# and a cancelled item needs a terminal status distinct from FAILED (a
# cancelled item didn't error, it was never asked to run).
CONTENT_BATCH_ITEM_STATUSES = (
    "PENDING", "GENERATING", "COMPLETED", "SCORED", "APPROVED", "REJECTED", "FAILED", "CANCELLED",
)

# Statuses an item can still be claimed *from* for a normal run or a
# cancel -- mirrors app.modules.batch.service.BATCH_ITEM_ENGINE_CLAIMABLE_STATUSES.
# Excludes GENERATING (already claimed/in flight) and every terminal status.
CONTENT_BATCH_ITEM_CLAIMABLE_STATUSES = ("PENDING",)
CONTENT_BATCH_ITEM_TERMINAL_STATUSES = ("APPROVED", "REJECTED", "FAILED", "CANCELLED")

DEFAULT_SCORE_THRESHOLD = 8.0  # 0-10 scale -- see service.py for why this differs from Task 05's own internal 0-90 QUALITY_PASS_THRESHOLD


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContentBatch(Base):
    """One "N ContentIdeas in, N scored+approved/rejected Stories out" run,
    all filed under one shared Video (see module docstring). `style`/
    `language` apply to every item's Story generation, matching how
    app.modules.batch.models.Batch's own `template_id` is applied once to
    every item. `score_threshold` is this task's own required "make the
    threshold configurable" -- 0-10 scale (the task's literal "8.0 / 10"),
    independent of Task 05's fixed, internal QUALITY_PASS_THRESHOLD.
    """

    __tablename__ = "content_batch"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), nullable=False)
    style: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="english")
    score_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=DEFAULT_SCORE_THRESHOLD)
    status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["ContentBatchItem"]] = relationship(
        "ContentBatchItem", back_populates="batch", order_by="ContentBatchItem.index"
    )


class ContentBatchItem(Base):
    """One ContentIdea -> one Story-generation-and-scoring attempt within a
    ContentBatch. `quality_score` is a denormalized copy of the winning
    StoryVersion's own `quality_score` (Task 05, 0-90 scale) -- safe to
    copy because a version's score is only ever overwritten by an explicit
    re-score (never silently changes underneath this row), and copying it
    avoids a cross-module join into ai.story on every batch list/detail
    read. `story_job_id`/`story_version_id` remain the canonical pointers
    back to the real generated content -- this table never duplicates
    title/script_text/the score breakdown itself (see module docstring's
    "Do not duplicate Story data" instruction).
    """

    __tablename__ = "content_batch_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("content_batch.id"), nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    idea_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    story_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    story_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    batch: Mapped[ContentBatch] = relationship("ContentBatch", back_populates="items")
