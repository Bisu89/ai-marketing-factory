from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

STORY_STYLES = ("emotional", "humorous", "inspirational", "dramatic", "educational", "sales")
STORY_LANGUAGES = ("english", "spanish", "vietnamese")
STORY_JOB_STATUSES = ("completed", "failed")

# Task 05 -- see app/modules/ai/story/quality.py. Sum of the 9 dimension
# scores (0-10 each), so the total range is 0-90; a version is worth
# rendering once ai-generated content clears this bar. A deliberate,
# documented judgment call (avg ~6.7/10 across every dimension), not a
# value the AI itself decides per-call -- computed in Python from the
# scores so the pass/fail line is consistent across every scoring call
# and every provider, not subject to the model's own inconsistent notion
# of "good enough."
QUALITY_SCORE_DIMENSIONS = (
    "hook", "curiosity", "emotion", "conflict", "twist",
    "ending", "shareability", "originality", "commercial_fit",
)
QUALITY_PASS_THRESHOLD = 60
QUALITY_RECOMMENDATIONS = ("pass", "fail")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StoryJob(Base):
    """One AI-Story generation run for a single library Video. Unlike
    SceneCutJob/VideoComposeJob, this has no background queue/worker -- an LLM
    text-generation call is fast enough (single-digit seconds) to run
    synchronously inside the request, so status is only ever "completed" or
    "failed" by the time the response is returned. Kept as its own table (not
    a column on Video) per the app/modules/ extensibility convention, and
    written purely for history/audit since the epic asked results be saved.
    """

    __tablename__ = "story_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("video.id"), nullable=False)

    style: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="english")
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # Task 04 -- optional provenance back to the app.modules.content_strategy
    # ContentIdea (if any) that supplied extra context to this generation.
    # Bare int, no FK/relationship -- ai/story must never import
    # content_strategy (per app/modules/README.md); same convention as
    # PublishLog.ai_story_job_id / BatchItem.project_id elsewhere in this
    # codebase. Null for every StoryJob created the plain way (POST
    # /story-jobs with no idea involved), which is most of them.
    content_idea_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    versions: Mapped[list["StoryVersion"]] = relationship(
        "StoryVersion", back_populates="job", order_by="StoryVersion.version_index"
    )


class StoryVersion(Base):
    """One of the (2, by default) narration-script variants produced by a
    single StoryJob generation call.

    Task 05 (see app/modules/ai/story/quality.py) adds 3 nullable quality-
    scoring columns directly here rather than a new table. Considered and
    rejected: (1) a new `story_quality_score` table -- rejected because
    there is no product need to keep more than the *latest* score per
    version (re-scoring is meant to fully replace the old verdict, same
    "regeneration atomically replaces" convention already used for
    Voice/Motion/Captions elsewhere in this codebase, not to accumulate a
    history no UI or workflow reads); (2) stuffing the score into
    `ai_generation_history.response_raw` alone -- rejected because that
    would make "does this version pass?" require parsing a JSON blob out
    of history on every read instead of a plain indexed column, and
    `ai_generation_history` is an append-only audit log, not meant to be
    queried for current state. `quality_score`/`quality_recommendation`
    are real columns (cheap to filter/sort by); the 9 individual dimension
    scores + reasoning + suggestions are bundled into one JSON column
    (`quality_breakdown`) since nothing needs to query a single dimension
    on its own -- same "structured but not over-normalized" shape already
    used by `Asset.extra_metadata`/`tags`.
    """

    __tablename__ = "story_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_job_id: Mapped[int] = mapped_column(ForeignKey("story_job.id"), nullable=False)
    version_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    script_text: Mapped[str] = mapped_column(String, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Null until scored at least once. A failed scoring attempt never
    # touches these -- see quality.py's own StoryQualityService.score()
    # docstring -- so a bad/timed-out call can't clobber a previously
    # valid score.
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[StoryJob] = relationship("StoryJob", back_populates="versions")
