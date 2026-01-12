"""
Schemas for Surfsense documentation.
"""

from pydantic import BaseModel, ConfigDict


class SurfsenseDocsChunkRead(BaseModel):
    """Schema for a Surfsense docs chunk."""

    id: int
    content: str

    model_config = ConfigDict(from_attributes=True)


class SurfsenseDocsDocumentWithChunksRead(BaseModel):
    """Schema for a Surfsense docs document with its chunks."""

    id: int
    title: str
    source: str
    content: str
    chunks: list[SurfsenseDocsChunkRead]

    model_config = ConfigDict(from_attributes=True)

