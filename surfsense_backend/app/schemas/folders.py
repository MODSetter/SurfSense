"""Pydantic schemas for folder CRUD, move, and reorder operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(max_length=255, min_length=1)
    parent_id: int | None = None
    search_space_id: int


class FolderUpdate(BaseModel):
    name: str = Field(max_length=255, min_length=1)


class FolderMove(BaseModel):
    new_parent_id: int | None = None


class FolderReorder(BaseModel):
    before_position: str | None = None
    after_position: str | None = None


class FolderRead(BaseModel):
    id: int
    name: str
    position: str
    parent_id: int | None
    search_space_id: int
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FolderBreadcrumb(BaseModel):
    id: int
    name: str


class DocumentMove(BaseModel):
    folder_id: int | None = None


class BulkDocumentMove(BaseModel):
    document_ids: list[int]
    folder_id: int | None = None
