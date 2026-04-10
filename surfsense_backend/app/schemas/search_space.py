import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .base import IDModel, TimestampModel


class SearchSpaceBase(BaseModel):
    name: str
    description: str | None = None


class SearchSpaceCreate(SearchSpaceBase):
    citations_enabled: bool = True
    qna_custom_instructions: str | None = None


class SearchSpaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    citations_enabled: bool | None = None
    qna_custom_instructions: str | None = None
    shared_memory_md: str | None = None


class SearchSpaceRead(SearchSpaceBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID
    citations_enabled: bool
    qna_custom_instructions: str | None = None
    shared_memory_md: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SearchSpaceWithStats(SearchSpaceRead):
    """Extended search space info with member count and ownership status."""

    member_count: int = 1
    is_owner: bool = False
