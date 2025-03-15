from pydantic import BaseModel
from .base import IDModel, TimestampModel

class PodcastBase(BaseModel):
    title: str
    is_generated: bool = False
    podcast_content: str = ""
    file_location: str = ""
    search_space_id: int

class PodcastCreate(PodcastBase):
    pass

class PodcastUpdate(PodcastBase):
    pass

class PodcastRead(PodcastBase, IDModel, TimestampModel):
    class Config:
        from_attributes = True 