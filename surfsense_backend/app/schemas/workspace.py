import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .base import IDModel, TimestampModel


class WorkspaceBase(BaseModel):
    name: str
    description: str | None = None


class WorkspaceCreate(WorkspaceBase):
    citations_enabled: bool = True
    qna_custom_instructions: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    citations_enabled: bool | None = None
    qna_custom_instructions: str | None = None


class WorkspaceApiAccessUpdate(BaseModel):
    api_access_enabled: bool


class WorkspaceRead(WorkspaceBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID
    citations_enabled: bool
    api_access_enabled: bool = False
    qna_custom_instructions: str | None = None
    shared_memory_md: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkspaceWithStats(WorkspaceRead):
    """Extended workspace info with member count and ownership status."""

    member_count: int = 1
    is_owner: bool = False
