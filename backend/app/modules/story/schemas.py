"""Pydantic I/O contracts for the story planning layer (feature 131).

Status / mode / scope strings are validated HERE (not a DB CHECK) --
matching every other status field in this codebase (e.g.
app.modules.factory.schemas, app.modules.publishing.schemas).

The named JSON bundles on Channel/Series (voice_config_json, branding_json,
...) are kept as free `dict` for Phase 1: their shapes settle in Phase 6
(the Channel -> Series -> Story config merge). Validating them now would be
guessing.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.story.models import (
    EPISODE_STATUSES,
    PRODUCTION_PROFILES,
    SCENE_TYPES,
    STORY_MODES,
    STORY_RUN_SCOPES,
    STORY_RUN_STATUSES,
    STORY_STATUSES,
    VISUAL_MODE_SOURCES,
    VISUAL_MODES,
)


def _one_of(field_name: str, allowed: tuple[str, ...]):
    """Build a functional pydantic-v2 field validator that rejects any
    value outside `allowed`. Used as `_x = field_validator("f")(_one_of(...))`.
    """

    def _v(cls, value: str) -> str:  # noqa: N805 -- pydantic functional-validator signature
        if value not in allowed:
            raise ValueError(f"{field_name} must be one of {allowed}, got {value!r}")
        return value

    return _v


# -- Channel --------------------------------------------------------------


class ChannelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    language: str = "en"
    locale: str | None = None
    niche: str | None = None
    voice_config_json: dict = Field(default_factory=dict)
    branding_json: dict = Field(default_factory=dict)
    visual_style_json: dict = Field(default_factory=dict)
    metadata_style_json: dict = Field(default_factory=dict)
    schedule_json: dict = Field(default_factory=dict)
    youtube_channel_pk: int | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Channel.name must not be blank")
        return value


class ChannelOut(ChannelIn):
    id: int
    created_at: datetime
    updated_at: datetime


# -- Episode ------------------------------------------------------------
#
# `series_id` is a bare int (app.modules.series.Series lives in another
# module -- this module never imports it, the same convention
# app.modules.beat.Project.series_id already uses). An Episode pointing at
# a series that doesn't exist is a harmless orphan, not an error worth a
# cross-module lookup here.


class EpisodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: int
    order: int
    title: str | None = None
    status: str = "PLANNED"

    _status_v = field_validator("status")(_one_of("Episode.status", EPISODE_STATUSES))

    @field_validator("order")
    @classmethod
    def _order_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Episode.order must be >= 1")
        return value


class EpisodeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    series_id: int
    order: int
    title: str | None
    status: str
    story_id: int | None
    compiled_project_ids_json: list = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# -- Story ------------------------------------------------------------


class StoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    mode: str = "STORY"
    episode_id: int | None = None
    logline: str | None = None
    genre: str | None = None
    story_bible_json: dict = Field(default_factory=dict)
    style_bible_json: dict = Field(default_factory=dict)
    # An app.modules.beat.schemas.ProjectConfig blob. Kept opaque here in
    # Phase 1 -- the Phase 2 story pipeline (a composition root, allowed to
    # import beat) validates/normalises it when it actually resolves the
    # config. `{}` means "use every ProjectConfig default".
    project_config_json: dict = Field(default_factory=dict)
    budget_usd: float | None = None
    production_profile: str = "BALANCED"
    reference_notes: str | None = None
    content_idea_id: int | None = None

    _mode_v = field_validator("mode")(_one_of("Story.mode", STORY_MODES))
    _profile_v = field_validator("production_profile")(_one_of("Story.production_profile", PRODUCTION_PROFILES))

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Story.title must not be blank")
        return value

    @field_validator("budget_usd")
    @classmethod
    def _budget_positive(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("Story.budget_usd must be > 0 if set")
        return value

class StoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    logline: str | None = None
    genre: str | None = None
    status: str | None = None
    story_bible_json: dict | None = None
    style_bible_json: dict | None = None
    project_config_json: dict | None = None
    budget_usd: float | None = None
    production_profile: str | None = None
    reference_notes: str | None = None
    episode_id: int | None = None

    @field_validator("status")
    @classmethod
    def _status_valid(cls, value: str | None) -> str | None:
        if value is not None and value not in STORY_STATUSES:
            raise ValueError(f"Story.status must be one of {STORY_STATUSES}, got {value!r}")
        return value

    @field_validator("production_profile")
    @classmethod
    def _profile_valid(cls, value: str | None) -> str | None:
        if value is not None and value not in PRODUCTION_PROFILES:
            raise ValueError(f"Story.production_profile must be one of {PRODUCTION_PROFILES}, got {value!r}")
        return value


class StoryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    episode_id: int | None
    mode: str
    title: str
    logline: str | None
    genre: str | None
    status: str
    story_bible_json: dict
    style_bible_json: dict
    project_config_json: dict
    budget_usd: float | None
    production_profile: str
    reference_notes: str | None
    content_idea_id: int | None
    created_at: datetime
    updated_at: datetime


# -- Character / Location ------------------------------------------------


class StoryCharacterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: str | None = None
    age: str | None = None
    gender: str | None = None
    appearance: str | None = None
    hairstyle: str | None = None
    face: str | None = None
    body: str | None = None
    wardrobe: str | None = None
    personality: str | None = None
    emotional_traits: str | None = None
    relationships_json: dict = Field(default_factory=dict)
    negative_constraints: str | None = None
    canonical_prompt_block: str | None = None
    reference_asset_id: int | None = None
    voice_id: str | None = None
    generation_metadata_json: dict = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("StoryCharacter.name must not be blank")
        return value


class StoryCharacterOut(StoryCharacterIn):
    id: int
    story_id: int
    created_at: datetime
    updated_at: datetime


class StoryLocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    lighting_default: str | None = None
    mood: str | None = None
    reference_asset_id: int | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("StoryLocation.name must not be blank")
        return value


class StoryLocationOut(StoryLocationIn):
    id: int
    story_id: int
    created_at: datetime
    updated_at: datetime


# -- Chapter / Scene --------------------------------------------------


class StoryChapterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int
    title: str | None = None
    summary: str | None = None
    goal: str | None = None
    retention_notes: str | None = None

    @field_validator("order")
    @classmethod
    def _order_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("StoryChapter.order must be >= 1")
        return value


class StoryChapterOut(StoryChapterIn):
    id: int
    story_id: int
    compiled_project_id: int | None
    created_at: datetime
    updated_at: datetime


class StorySceneIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int
    scene_type: str | None = None
    narration: str | None = None
    dialogue_json: list = Field(default_factory=list)
    character_ids_json: list = Field(default_factory=list)
    location_id: int | None = None
    image_prompt: str | None = None
    video_prompt: str | None = None
    visual_mode: str = "STILL_WITH_MOTION"
    visual_mode_source: str = "AUTO"
    motion_preset: str | None = None
    camera: str | None = None
    lighting: str | None = None
    emotion: str | None = None
    time_of_day: str | None = None
    continuity_notes: str | None = None
    duration_hint: float = 6.0

    _vm_v = field_validator("visual_mode")(_one_of("StoryScene.visual_mode", VISUAL_MODES))
    _vms_v = field_validator("visual_mode_source")(_one_of("StoryScene.visual_mode_source", VISUAL_MODE_SOURCES))

    @field_validator("scene_type")
    @classmethod
    def _known_scene_type(cls, value: str | None) -> str | None:
        if value is not None and value not in SCENE_TYPES:
            raise ValueError(f"StoryScene.scene_type must be one of {SCENE_TYPES}, got {value!r}")
        return value

    @field_validator("order")
    @classmethod
    def _order_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("StoryScene.order must be >= 1")
        return value

    @field_validator("duration_hint")
    @classmethod
    def _duration_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("StoryScene.duration_hint must be > 0")
        return value


class StorySceneOut(StorySceneIn):
    id: int
    chapter_id: int
    importance_score: int | None
    emotion_score: int | None
    movement_score: int | None
    complexity_score: int | None
    composite_score: int | None
    est_cost_usd: float | None
    image_asset_id: int | None
    video_asset_id: int | None
    reuse_asset_from_scene_id: int | None
    approved: bool
    created_at: datetime
    updated_at: datetime


# -- StoryRun / StoryCheckpoint (read-only in Phase 1) ------------------


class StoryCheckpointOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    story_run_id: int
    stage: str
    status: str
    attempt: int
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None
    checkpoint_metadata_json: dict | None

    @field_validator("stage")
    @classmethod
    def _known_stage(cls, value: str) -> str:
        return value  # not enforced on read -- a stage name may be added later


class StoryRunOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    story_id: int
    scope: str
    status: str
    failed_stage: str | None
    error_code: str | None
    error_message: str | None
    attempt: int
    target_language: str | None
    stage_metrics_json: dict | None
    est_cost_json: dict | None
    actual_cost_usd: float | None
    compiled_project_ids_json: list
    requires_human_review: bool
    review_reason_count: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime

    _scope_v = field_validator("scope")(_one_of("StoryRun.scope", STORY_RUN_SCOPES))
    _status_v = field_validator("status")(_one_of("StoryRun.status", STORY_RUN_STATUSES))
