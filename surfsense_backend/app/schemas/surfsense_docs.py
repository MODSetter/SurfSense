"""
Schemas for Neonote documentation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NeonoteDocsChunkRead(BaseModel):
    """Schema for a Neonote docs chunk."""

    id: int
    content: str

    model_config = ConfigDict(from_attributes=True)


class NeonoteDocsDocumentRead(BaseModel):
    """Schema for a Neonote docs document (without chunks)."""

    id: int
    title: str
    source: str
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class NeonoteDocsDocumentWithChunksRead(BaseModel):
    """Schema for a Neonote docs document with its chunks."""

    id: int
    title: str
    source: str
    content: str
    chunks: list[NeonoteDocsChunkRead]

    model_config = ConfigDict(from_attributes=True)
