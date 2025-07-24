import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .base import IDModel, TimestampModel


class SearchSpaceBase(BaseModel):
    name: str
    description: str | None = None


class SearchSpaceCreate(SearchSpaceBase):
    pass


class SearchSpaceUpdate(SearchSpaceBase):
    pass


class SearchSpaceRead(SearchSpaceBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
