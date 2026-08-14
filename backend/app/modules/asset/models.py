from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ASSET_TYPES = ("image", "video", "audio")

# Task 15 (see docs/features/41-local-asset-ingestion.md) -- a stored,
# Re-scan-refreshed classification of whether the file backing an Asset row
# is still there and still openable. Deliberately NOT the same thing as
# Asset.is_ready below: is_ready is a live, always-current
# Path.exists() check (can't go stale, but can't tell "missing" from
# "corrupt" either); `status` is a point-in-time verdict from the last
# import/re-scan, refreshed on demand rather than on every read.
ASSET_STATUSES = ("ACTIVE", "MISSING", "INVALID")

ORIENTATIONS = ("PORTRAIT", "LANDSCAPE", "SQUARE")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Asset(Base):
    """One reusable local media file in the Video Factory's asset library --
    a still image, video clip, or audio file that a future Beat/Motion step
    can pick for a beat. Its own table, no FK into the core Video/Channel
    schema and no FK into any other module's tables -- per the
    app/modules/ extensibility convention, this module must stay fully
    self-contained (see app/modules/asset/README-equivalent note in
    docs/features/). `source`/`source_ref` record provenance (e.g. an
    uploaded file, or a Library video an asset was cut from) as plain
    strings rather than a real foreign key, so this table has zero schema
    dependency on any other table in the database.

    Task 15 adds ingestion-derived metadata (content_hash, orientation,
    category, emotion, status, thumbnail_path) directly as columns on this
    same table -- not a second Asset-like model -- since bulk local import
    is just a new, richer way to populate rows this table already had. See
    docs/features/41-local-asset-ingestion.md for why each column exists
    and why `category`/`emotion` are plain strings (reusing the *values*
    from the existing core `app.models.category.Category`/
    `app.models.emotion.Emotion` catalogs, duplicated as constants in
    ingest.py rather than imported -- a real FK would break this module's
    "own table, no FK into any other module" self-containment rule, since
    Category/Emotion live in the core `app.models` package, not in this
    module).
    """

    __tablename__ = "asset"
    __table_args__ = (
        # Every one of these backs a real filter this module's own
        # search()/list endpoints use (see service.py) -- not speculative;
        # Task 15's own instruction is "use actual query patterns to
        # justify indexes," not add them blindly.
        Index("ix_asset_content_hash", "content_hash"),
        Index("ix_asset_orientation", "orientation"),
        Index("ix_asset_category", "category"),
        Index("ix_asset_emotion", "emotion"),
        Index("ix_asset_source", "source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    # Absolute, resolved path -- unique so the same physical file can't be
    # registered twice under different spellings (see
    # AssetService._normalize_path).
    path: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String, nullable=False)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    filesize_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # JSON list[str], not a tag/asset_tag join table -- Asset tags are
    # free-form search keywords, not the curated, mergeable Tag dimension
    # `app/models/tag.py` already owns for Library videos. Reusing that
    # table would couple this module to a workflow (tag merge, get-or-create
    # by name) it doesn't need; a plain JSON column keeps the table
    # completely self-contained.
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    source: Mapped[str] = mapped_column(String, nullable=False, default="upload")
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    # Free-form extra fields a caller wants to keep alongside an asset
    # (e.g. {"camera": "phone", "orientation": "portrait"}) without needing
    # a schema change for every new attribute someone wants to search/filter
    # on later.
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # -- Task 15: ingestion-derived metadata (all nullable -- every asset
    # registered before this task, or via the plain POST /assets endpoint,
    # simply has none of it, exactly like `config` on a pre-Task-12
    # BeatPlan) ----------------------------------------------------------
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    orientation: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    emotion: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    @property
    def is_ready(self) -> bool:
        """Whether the underlying file is still present on disk right now --
        computed on read, never stored, so it can't go stale relative to the
        real filesystem (a file can be moved/deleted outside this app).
        This is the "asset preparation information" a future render step
        checks before trying to use an Asset.
        """
        return Path(self.path).exists()

    @property
    def effective_status(self) -> str:
        """`status` (below) merged with a live is_ready check -- a file that
        vanished since the last import/re-scan is reported MISSING
        immediately, without waiting for the next explicit Re-scan, while a
        file ffprobe/Pillow couldn't open at import time stays INVALID until
        Re-scan finds it healthy again. Never returns a stale ACTIVE for a
        file that's actually gone right now.
        """
        if not self.is_ready:
            return "MISSING"
        return self.status or "ACTIVE"

    @property
    def aspect_ratio(self) -> float | None:
        if not self.width or not self.height:
            return None
        return self.width / self.height

    @property
    def orientation_computed(self) -> str | None:
        """Derived fresh from width/height whenever both are known, instead
        of always trusting the stored `orientation` column -- so an asset
        registered through the old bare POST /assets (which never sets
        `orientation`) still reports a correct value if width/height happen
        to be supplied, and a stored value never silently disagrees with
        its own dimensions.
        """
        if self.orientation:
            return self.orientation
        if not self.width or not self.height:
            return None
        if self.width == self.height:
            return "SQUARE"
        return "PORTRAIT" if self.height > self.width else "LANDSCAPE"


IMPORT_JOB_STATUSES = ("QUEUED", "RUNNING", "COMPLETED", "CANCELLED", "FAILED")


class AssetImportJob(Base):
    """One run of "Add Files" / "Import Folder" (Task 15) -- its own table
    (own background thread, spawned on demand exactly like
    app.modules.batch's beat-generation thread, not a second general-
    purpose queue/worker service; see import_service.py's own module
    docstring) so GET /assets/import/{job_id} can poll real, durable
    progress instead of an in-memory-only, request-scoped guess. `failed_files`
    is a JSON list of {"path": ..., "reason": ...} -- Task 15 section 30's
    "report failed files with reason," not just a bare count.
    """

    __tablename__ = "asset_import_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="QUEUED")
    # A folder path for a folder import, or a short "N files" label for an
    # explicit-file-list import -- display only, never parsed back (use
    # import_root below to recover the real folder path programmatically).
    source_label: Mapped[str] = mapped_column(String, nullable=False)
    # The folder path this job was run against, or None for an explicit-
    # file-list import -- kept as its own field (not re-derived from
    # source_label, which is display text) so folder-tag derivation
    # (ingest.folder_tags_from_path) has an unambiguous root to work from.
    import_root: Mapped[str | None] = mapped_column(String, nullable=True)

    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    current_file: Mapped[str | None] = mapped_column(String, nullable=True)
    # default=list (not nullable=True with no default) -- AssetImportJobOut
    # always wants a real (possibly empty) list, never None, from the
    # moment a job is created.
    failed_files: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
