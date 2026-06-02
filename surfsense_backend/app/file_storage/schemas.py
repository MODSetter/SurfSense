"""API shapes for document file metadata."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.file_storage.persistence.enums import DocumentFileKind


class DocumentFileRead(BaseModel):
    """Lightweight metadata for one stored document file (no bytes)."""

    id: int
    document_id: int
    kind: DocumentFileKind
    original_filename: str
    mime_type: str | None = None
    size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
