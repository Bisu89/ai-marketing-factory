"""A named, independently-persisted BeatPlan+ProjectConfig -- the real
per-project storage Task 13's batch creation needs (see
docs/features/40-batch-video-creation.md).

Key architectural note: before this task, this app had NO multi-project
store at all -- the entire Video Factory worked against one singleton
`beats.json` (see router.py's own module docstring, still true and
unchanged: that endpoint and its file are untouched by this addition).
Batch creation fundamentally requires many independent, simultaneously-
existing beat plans (one per script), which a single file can't provide,
so this is genuinely new, necessary infrastructure -- not a redesign of
the existing single-project editing workflow, which keeps working exactly
as before, completely independent of this table.

Per app/modules/README.md, this module's own SQLAlchemy usage follows the
same pattern every other module already uses (video_composer, asset,
ai/story) -- its own table(s), no FK into the core Video/Channel schema.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """One independently-addressable project: a full BeatPlan (script_text/
    beats/project_name/config, see schemas.py) serialized as one JSON blob
    -- same "one JSON column instead of a dozen parallel ones" convention
    already used for VideoComposeJob.composition_request_json. A project
    created outside of a batch (not this task's own scope to build a UI
    for, but the model doesn't prevent it) is just as valid -- batch_id
    isn't even a field here; app.modules.batch.models.BatchItem carries the
    reverse reference instead (bare int, no FK/import -- see that module).
    """

    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Filesystem/URL-safe, globally unique -- see router.py's _unique_slug.
    # Not currently used as a real directory name anywhere (rendering still
    # organizes output by VideoComposeJob.id, unchanged), but kept ready
    # for exactly that per this task's "output organized by project" intent
    # without renaming video_composer's own, already-shipped, unrelated
    # job-numbered layout.
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # A full serialized BeatPlan (script_text/beats/project_name/config) --
    # validated against that Pydantic contract on every read and write
    # (see router.py), never trusted as pre-validated just because it's
    # already in the database.
    beat_plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Bare, unconstrained reference to a video_composer.models.VideoComposeJob.id
    # -- no FK/import (app.modules.beat must never import app.modules.video_composer).
    # Set once a render has actually been started for this project; a
    # project can be re-rendered, so this always reflects the *latest*
    # attempt, not a history (VideoComposeJob's own table is that history).
    render_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
