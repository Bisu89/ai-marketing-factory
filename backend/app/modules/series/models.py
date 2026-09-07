"""Series (scoped-down "100-Day Series"): a persistent name + character/
visual description that N independently-authored Projects (each created and
scripted exactly like today's existing "New Video" flow -- no AI-planned
story arc) can attach to, so their AI-generated images share one character
description. This module owns only Series bookkeeping -- it never imports
app.modules.beat (per app/modules/README.md); every reference to a Project
below is a bare, unconstrained int, the same "cross-module reference without
a real FK" convention already used throughout this codebase (see
app.modules.batch.models' own identical reasoning). The actual cross-module
orchestration (attaching a Project to a Series, folding the character
description into that Project's own image prompt config) lives in the
composition root -- app/api/v1/endpoints/series_project.py -- the only place
allowed to import both this module and app.modules.beat at once.

No status/state machine: unlike Batch (a bounded "N scripts in, N projects
out" run that eventually finishes), a Series is a standing container that
never "completes" -- episodes get attached to it indefinitely.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Free-text character/visual description (e.g. "male, 28, short messy
    # hair, grey hoodie, average build") -- folded into every attached
    # episode's own VisualGenerationProjectConfig.image_style_prompt at
    # attach time (see series_project.py), the same free-text style-suffix
    # mechanism this codebase already uses for per-project style
    # consistency (app.modules.beat.schemas.VisualGenerationProjectConfig).
    # This is style-level consistency, not a guarantee of pixel-identical
    # faces across episodes -- no reference-image/seed/embedding mechanism
    # exists in this codebase's image generation today.
    #
    # AI Storytelling Studio note (feature 131): superseded going forward by
    # app.modules.story.StoryCharacter -- kept, still written by the classic
    # series_project.py flow, no data migration.
    character_description: Mapped[str] = mapped_column(String, nullable=False, default="")

    # -- AI Storytelling Studio, Phase 1 (feature 131) -- additive.
    # `channel_id` -> app.modules.story.Channel.id (bare int, no FK -- Channel
    # is in another module, same convention as app.modules.beat.Project.series_id).
    # None for every Series created by the classic flow (backward compatible).
    # The *_json bundles override the parent Channel's own defaults; empty
    # dict = "inherit from Channel". Shape validated in schemas.py.
    channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    narrative_identity: Mapped[str | None] = mapped_column(String, nullable=True)
    visual_identity_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    voice_override_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_conventions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
