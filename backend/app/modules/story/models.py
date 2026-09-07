"""AI Storytelling Studio -- the story planning layer (plan Phase 1, see
docs/features/131-*). Channel -> Series -> Episode -> Story ->
Chapter -> Scene, plus Character / Location bibles and a resumable
StoryRun (a 1:1 mirror of app.modules.factory.FactoryRun /
FactoryCheckpoint).

Module rules (app/modules/README.md): this module owns its own tables and
never imports another module. FKs *within* this module are real; every
reference *out* of it is a bare, unconstrained int, the same
"cross-module reference without a real FK" convention used throughout this
codebase (app.modules.factory.FactoryRun.project_id,
app.modules.beat.Project.series_id, app.modules.batch.BatchItem.*, ...):

  Channel.youtube_channel_pk   -> app.modules.publishing.YouTubeChannel.id
  Episode.series_id            -> app.modules.series.Series.id
  Story.content_idea_id        -> app.modules.content_strategy.ContentIdea.id
  StoryCharacter.reference_asset_id / StoryLocation.reference_asset_id
  StoryScene.image_asset_id / video_asset_id
                               -> app.modules.asset.Asset.id
  StoryScene.reuse_asset_from_scene_id  -> another StoryScene.id (bare, like
                                           VideoComposeJob.previous_job_id)
  *compiled_project_id(s)      -> app.modules.beat.Project.id

Status / mode / scope vocabularies are validated in schemas.py (Pydantic),
never a DB CHECK constraint -- same pattern as every other status field in
this codebase.

No wiring into the render pipeline yet. Nothing consumes these tables --
Phase 2 builds the planning pipeline on top.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# -- Vocabularies (validated in schemas.py, not the DB) -------------------

STORY_MODES = ("STORY", "HISTORY", "EDUCATION")
PRODUCTION_PROFILES = ("ECONOMY", "BALANCED", "PREMIUM")

STORY_STATUSES = (
    "DRAFT",
    "DEVELOPING",       # STORY_DEVELOPMENT / STORY_BIBLE in progress
    "BIBLE_READY",      # bible + characters approved
    "SCENES_READY",     # chapters + scenes + classification approved
    "PRODUCING",        # a PRODUCE StoryRun is active
    "COMPLETED",
    "ARCHIVED",
)

EPISODE_STATUSES = ("PLANNED", "IN_PRODUCTION", "PRODUCED", "PUBLISHED", "ARCHIVED")

SCENE_TYPES = (
    "HOOK", "SETUP", "BUILD", "REVEAL", "CLIMAX", "TWIST",
    "REACTION", "CONFRONTATION", "TRANSITION", "ENDING", "BODY",
)
VISUAL_MODES = ("STILL", "STILL_WITH_MOTION", "AI_VIDEO")
VISUAL_MODE_SOURCES = ("AUTO", "USER")

# -- StoryRun: mirrors app.modules.factory.models ------------------------

STORY_RUN_SCOPES = ("STORY_PLAN", "RESEARCH", "LOCALIZE", "PRODUCE")

# STORY_PLAN scope stages (Phase 2). PRODUCE scope reuses the factory
# stage names once a Project is compiled (Phase 5). Kept as one flat tuple
# -- a StoryRun's "coarse status" and "current stage" are the same thing
# while it is progressing, exactly like FactoryRun.status.
STORY_RUN_STATUSES = (
    "DRAFT",
    "IDEA",
    "STORY_DEVELOPMENT",
    "STORY_BIBLE",
    "CHARACTER_BIBLE",
    "CHAPTER_OUTLINE",
    "SCENE_BREAKDOWN",
    "SCENE_CLASSIFICATION",
    "VISUAL_PLANNING",
    "COMPILING",
    "NEEDS_REVIEW",
    "READY",
    "PRODUCING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
)
STORY_RUN_ACTIVE_STATUSES = tuple(
    s for s in STORY_RUN_STATUSES if s not in ("COMPLETED", "FAILED", "CANCELLED")
)
STORY_RUN_STAGES = tuple(
    s for s in STORY_RUN_STATUSES if s not in ("DRAFT", "NEEDS_REVIEW", "READY", "COMPLETED", "FAILED", "CANCELLED")
)
STORY_MAX_ATTEMPTS = 3

CHECKPOINT_PENDING = "PENDING"
CHECKPOINT_RUNNING = "RUNNING"
CHECKPOINT_COMPLETED = "COMPLETED"
CHECKPOINT_FAILED = "FAILED"
CHECKPOINT_SKIPPED = "SKIPPED"
STORY_CHECKPOINT_STATUSES = (
    CHECKPOINT_PENDING, CHECKPOINT_RUNNING, CHECKPOINT_COMPLETED, CHECKPOINT_FAILED, CHECKPOINT_SKIPPED,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StoryChannel(Base):
    """One publishing brand: a language + locale + a bundle of default
    branding/voice/style/metadata/schedule config that merges down onto
    every Story produced under it (Channel defaults -> Series overrides ->
    Story overrides -- the merge itself is Phase 6, not here).

    `youtube_channel_pk` links to a real connected
    app.modules.publishing.YouTubeChannel row (bare int, no FK) once the
    user connects one -- None means "not connected to YouTube yet".

    Table is `story_channel`, not `channel` -- `channel` is already taken by
    the core `app.models.channel.Channel` (the platform channel a
    downloaded video belongs to), an unrelated concept.
    """

    __tablename__ = "story_channel"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    locale: Mapped[str | None] = mapped_column(String, nullable=True)
    niche: Mapped[str | None] = mapped_column(String, nullable=True)

    # Named JSON bundles -- shape defined/validated in schemas.py. Empty
    # dict = "inherit system defaults".
    voice_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    branding_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    visual_style_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_style_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schedule_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # -> app.modules.publishing.YouTubeChannel.id (bare, no FK/import).
    youtube_channel_pk: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Episode(Base):
    """One numbered slot in a Series. `series_id` is a bare int
    (app.modules.series.Series lives in another module). `story_id` points
    at the Story being (or already) produced for this slot -- None while
    the episode is only planned. `compiled_project_ids_json` is the list of
    app.modules.beat.Project ids a produce run created (one per chapter, or
    one for the whole story -- see StoryCompileProjectConfig.compile_mode).
    """

    __tablename__ = "episode"

    id: Mapped[int] = mapped_column(primary_key=True)
    # -> app.modules.series.Series.id (bare, no FK -- another module).
    series_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PLANNED")

    story_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compiled_project_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Story(Base):
    """The planning container. `project_config_json` is a full
    app.modules.beat.schemas.ProjectConfig serialised as one blob (the
    same "one JSON column, not a dozen tables" convention BeatPlan.config
    already uses) -- the composition root validates it against that
    Pydantic contract on read/write, never trusting it as pre-validated.

    `story_bible_json` / `style_bible_json` are nested value objects
    (genre/tone/themes/world/timeline/style) with no independent lifecycle
    -- also blobs, also validated by schemas.py.
    """

    __tablename__ = "story"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Real FK -- Episode is in this same module. Nullable: a Story can be a
    # standalone experiment not attached to any Series/Episode.
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episode.id"), nullable=True, index=True)

    mode: Mapped[str] = mapped_column(String, nullable=False, default="STORY")
    title: Mapped[str] = mapped_column(String, nullable=False)
    logline: Mapped[str | None] = mapped_column(Text, nullable=True)
    genre: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT", index=True)

    story_bible_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    style_bible_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    project_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    budget_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    production_profile: Mapped[str] = mapped_column(String, nullable=False, default="BALANCED")

    # Free-text research/reference notes the user pastes in for HISTORY /
    # EDUCATION mode (never a URL the app fetches -- see the plan's
    # originality/copyright sections). Only ever fed to the
    # STORY_DEVELOPMENT stage, never to per-scene prompts.
    reference_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -> app.modules.content_strategy.ContentIdea.id (bare, no FK). Set
    # when a Story is spun out of a planned Content Idea; None otherwise.
    content_idea_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    characters: Mapped[list["StoryCharacter"]] = relationship(
        "StoryCharacter", back_populates="story", cascade="all, delete-orphan", order_by="StoryCharacter.id"
    )
    locations: Mapped[list["StoryLocation"]] = relationship(
        "StoryLocation", back_populates="story", cascade="all, delete-orphan", order_by="StoryLocation.id"
    )
    chapters: Mapped[list["StoryChapter"]] = relationship(
        "StoryChapter", back_populates="story", cascade="all, delete-orphan", order_by="StoryChapter.order"
    )


class StoryCharacter(Base):
    """One character's canonical description. `canonical_prompt_block` is
    composed once (from the structured fields below) and then LOCKED --
    every scene the character appears in reuses this exact block so the
    character doesn't drift between AI-generated images. `reference_asset_id`
    (bare Asset.id) is an optional approved portrait.
    """

    __tablename__ = "story_character"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("story.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    age: Mapped[str | None] = mapped_column(String, nullable=True)
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    hairstyle: Mapped[str | None] = mapped_column(String, nullable=True)
    face: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(String, nullable=True)
    wardrobe: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotional_traits: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationships_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    negative_constraints: Mapped[str | None] = mapped_column(Text, nullable=True)

    canonical_prompt_block: Mapped[str | None] = mapped_column(Text, nullable=True)
    # -> app.modules.asset.Asset.id (bare, no FK).
    reference_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The voice used for this character's dialogue (Phase 7 multi-voice);
    # a plain provider voice id string, not an Asset.
    voice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    generation_metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    story: Mapped["Story"] = relationship("Story", back_populates="characters")


class StoryLocation(Base):
    __tablename__ = "story_location"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("story.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lighting_default: Mapped[str | None] = mapped_column(String, nullable=True)
    mood: Mapped[str | None] = mapped_column(String, nullable=True)
    # -> app.modules.asset.Asset.id (bare, no FK).
    reference_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    story: Mapped["Story"] = relationship("Story", back_populates="locations")


class StoryChapter(Base):
    """One chapter. `compiled_project_id` (bare Project.id) is set once a
    PRODUCE run has compiled this chapter into a renderable Project (for
    compile_mode == "per_chapter"); None for "single" mode (where the whole
    story is one Project, tracked on the Episode instead).
    """

    __tablename__ = "story_chapter"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("story.id"), nullable=False, index=True)

    order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # -> app.modules.beat.Project.id (bare, no FK).
    compiled_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    story: Mapped["Story"] = relationship("Story", back_populates="chapters")
    scenes: Mapped[list["StoryScene"]] = relationship(
        "StoryScene", back_populates="chapter", cascade="all, delete-orphan", order_by="StoryScene.order"
    )


class StoryScene(Base):
    """One scene -- roughly app.modules.beat.schemas.Beat extended with the
    Scene Director fields and multi-character dialogue. StoryScene -> Beat
    is a mechanical mapping at compile time (many fields share names).

    `visual_mode_source == "USER"` freezes `visual_mode` -- a re-run of the
    Scene Director never touches a scene a human has overridden.
    """

    __tablename__ = "story_scene"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("story_chapter.id"), nullable=False, index=True)

    order: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_type: Mapped[str | None] = mapped_column(String, nullable=True)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{"character_id": int, "line": str}, ...]
    dialogue_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [character_id, ...] -- which characters are on screen this scene.
    character_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("story_location.id"), nullable=True)

    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_mode: Mapped[str] = mapped_column(String, nullable=False, default="STILL_WITH_MOTION")
    visual_mode_source: Mapped[str] = mapped_column(String, nullable=False, default="AUTO")
    motion_preset: Mapped[str | None] = mapped_column(String, nullable=True)

    camera: Mapped[str | None] = mapped_column(String, nullable=True)
    lighting: Mapped[str | None] = mapped_column(String, nullable=True)
    emotion: Mapped[str | None] = mapped_column(String, nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String, nullable=True)
    continuity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_hint: Mapped[float] = mapped_column(Float, nullable=False, default=6.0)

    # Scene Director scores (0-100). None until SCENE_CLASSIFICATION runs.
    importance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    emotion_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movement_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    complexity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    composite_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    est_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # -> app.modules.asset.Asset.id (bare, no FK). Set by ASSET_GENERATION.
    image_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # -> another StoryScene.id (bare, like VideoComposeJob.previous_job_id).
    reuse_asset_from_scene_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    chapter: Mapped["StoryChapter"] = relationship("StoryChapter", back_populates="scenes")


class StoryRun(Base):
    """One resumable "advance this story" run -- a 1:1 mirror of
    app.modules.factory.models.FactoryRun. `scope` says what kind of run
    (plan / research / localize / produce); `status` holds the full
    granular stage directly; `failed_stage` remembers where a FAILED run
    stopped so Retry resumes from the right place.

    `story_id` is a real FK -- Story is in this same module (unlike
    FactoryRun.project_id, which crosses into app.modules.beat).
    """

    __tablename__ = "story_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("story.id"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String, nullable=False, default="STORY_PLAN")
    status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT", index=True)
    failed_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # For scope=LOCALIZE, which language this run produces.
    target_language: Mapped[str | None] = mapped_column(String, nullable=True)

    # Named seconds-elapsed floats per stage (diagnostics, not analytics --
    # same convention as FactoryRun.metrics).
    stage_metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # The pre-flight CostEstimate (see app.modules.ai.cost_estimator),
    # cached for cheap reporting; actual_cost_usd is filled after the run.
    est_cost_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actual_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    # app.modules.beat.Project ids this run compiled/produced (bare ints).
    compiled_project_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_reason_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, index=True
    )

    checkpoints: Mapped[list["StoryCheckpoint"]] = relationship(
        "StoryCheckpoint", back_populates="run", cascade="all, delete-orphan", order_by="StoryCheckpoint.id"
    )


class StoryCheckpoint(Base):
    """A durable per-(run, stage) audit record -- 1:1 mirror of
    app.modules.factory.models.FactoryCheckpoint. Real FK to story_run.id
    (same module). One row per (story_run_id, stage); a retry re-enters the
    same row (bumping `attempt`) rather than appending.
    """

    __tablename__ = "story_checkpoint"

    id: Mapped[int] = mapped_column(primary_key=True)
    story_run_id: Mapped[int] = mapped_column(ForeignKey("story_run.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=CHECKPOINT_PENDING)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    # Small stage facts only, never a full bible/plan (e.g.
    # {"scenes_done": [1,2,3], "scenes_billed": 3}).
    checkpoint_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    run: Mapped["StoryRun"] = relationship("StoryRun", back_populates="checkpoints")
