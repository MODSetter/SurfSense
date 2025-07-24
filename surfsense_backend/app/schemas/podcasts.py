from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .base import IDModel, TimestampModel


class PodcastBase(BaseModel):
    title: str
    podcast_transcript: list[Any]
    file_location: str = ""
    search_space_id: int


class PodcastCreate(PodcastBase):
    pass


class PodcastUpdate(PodcastBase):
    pass


class PodcastRead(PodcastBase, IDModel, TimestampModel):
    model_config = ConfigDict(from_attributes=True)


class PodcastGenerateRequest(BaseModel):
    type: Literal["DOCUMENT", "CHAT"]
    ids: list[int]
    search_space_id: int
    podcast_title: str = "SurfSense Podcast"
