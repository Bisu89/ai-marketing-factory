from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.ai.story.models import STORY_LANGUAGES, STORY_STYLES, StoryJob, StoryVersion


class StoryGenerateIn(BaseModel):
    video_id: int
    style: str
    language: str = "english"

    @field_validator("style")
    @classmethod
    def _valid_style(cls, value: str) -> str:
        if value not in STORY_STYLES:
            raise ValueError(f"Invalid style {value!r}, must be one of {STORY_STYLES}")
        return value

    @field_validator("language")
    @classmethod
    def _valid_language(cls, value: str) -> str:
        if value not in STORY_LANGUAGES:
            raise ValueError(f"Invalid language {value!r}, must be one of {STORY_LANGUAGES}")
        return value


class StoryVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_index: int
    title: str
    script_text: str
    is_selected: bool
    # Task 05 -- null until POST .../score has been called at least once.
    # quality_score is the 0-90 total (sum of 9 0-10 dimension scores);
    # quality_breakdown carries the per-dimension scores, reasoning, and
    # improvement suggestions (see StoryQualityService.score()).
    quality_score: float | None = None
    quality_recommendation: str | None = None
    quality_breakdown: dict | None = None
    quality_scored_at: datetime | None = None


class StoryJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    style: str
    language: str
    status: str
    error_message: str | None
    content_idea_id: int | None = None
    created_at: datetime
    versions: list[StoryVersionOut] = []


def job_to_out(job: StoryJob) -> StoryJobOut:
    return StoryJobOut.model_validate(job)


def version_to_out(version: StoryVersion) -> StoryVersionOut:
    return StoryVersionOut.model_validate(version)
