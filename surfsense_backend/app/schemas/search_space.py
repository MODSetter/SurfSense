from datetime import datetime
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict
from .base import IDModel, TimestampModel

class SearchSpaceBase(BaseModel):
    name: str
    description: Optional[str] = None

class SearchSpaceCreate(SearchSpaceBase):
    pass

class SearchSpaceUpdate(SearchSpaceBase):
    pass

class SearchSpaceRead(SearchSpaceBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True) 