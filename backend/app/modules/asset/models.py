from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ASSET_TYPES = ("image", "video", "audio")


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
    """

    __tablename__ = "asset"

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
