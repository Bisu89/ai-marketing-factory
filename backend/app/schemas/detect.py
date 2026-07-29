from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class VideoInfoOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    thumbnail_url: str = Field(alias="thumbnailUrl")
    author: str
    views: int
    upload_date: str = Field(alias="uploadDate")
    duration_sec: int = Field(alias="durationSec")
    original_url: str = Field(alias="originalUrl")


class SingleVideoResultOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content_type: Literal["video"] = Field(alias="contentType")
    platform: str
    video: VideoInfoOut


class CollectionResultOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content_type: Literal["playlist", "channel"] = Field(alias="contentType")
    platform: str
    title: str
    author: str
    videos: list[VideoInfoOut]


DetectResultOut = Union[SingleVideoResultOut, CollectionResultOut]


class DetectRequest(BaseModel):
    url: HttpUrl
