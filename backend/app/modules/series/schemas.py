from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

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
    created_at: datetime
    updated_at: datetime
