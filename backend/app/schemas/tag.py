from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


class TagCreateIn(BaseModel):
    name: str


class TagRenameIn(BaseModel):
    name: str


class TagMergeIn(BaseModel):
    source_tag_id: int
    target_tag_id: int


class VideoTagsIn(BaseModel):
    tag_names: list[str]
