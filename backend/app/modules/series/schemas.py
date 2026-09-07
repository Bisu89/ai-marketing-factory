from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_SERIES_NAME_LEN = 120


class CreateSeriesRequest(BaseModel):
    name: str
    character_description: str = ""

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Series name must not be blank")
        if len(value) > MAX_SERIES_NAME_LEN:
            raise ValueError(f"Series name must be at most {MAX_SERIES_NAME_LEN} characters")
        return value


class UpdateSeriesRequest(BaseModel):
    name: str
    character_description: str = ""

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Series name must not be blank")
        if len(value) > MAX_SERIES_NAME_LEN:
            raise ValueError(f"Series name must be at most {MAX_SERIES_NAME_LEN} characters")
        return value


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    character_description: str
    # AI Storytelling Studio, Phase 1 (feature 131) -- additive. `channel_id`
    # -> app.modules.story.StoryChannel.id (bare int, no FK/import). Empty
    # dict = "inherit from the parent Channel".
    channel_id: int | None = None
    narrative_identity: str | None = None
    visual_identity_json: dict = Field(default_factory=dict)
    voice_override_json: dict = Field(default_factory=dict)
    metadata_conventions_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UpdateSeriesStudioRequest(BaseModel):
    """Patch only the feature-131 columns -- never name /
    character_description (the classic flow owns those).
    """

    model_config = ConfigDict(extra="forbid")

    channel_id: int | None = None
    narrative_identity: str | None = None
    visual_identity_json: dict = Field(default_factory=dict)
    voice_override_json: dict = Field(default_factory=dict)
    metadata_conventions_json: dict = Field(default_factory=dict)
