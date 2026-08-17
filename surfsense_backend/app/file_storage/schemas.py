"""API shapes for document file metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

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


class DocumentViewFileRead(BaseModel):
    """One stored original in the frontend's domain-neutral viewer shape."""

    file_id: int
    filename: str
    mime_type: str
    size_bytes: int
    content_url: str


class DocumentViewManifestRead(BaseModel):
    """Server-authoritative choice between an original file and text content."""

    document_id: int
    title: str
    document_type: str
    status: str
    presentation: Literal["original", "text", "missing_original"]
    file: DocumentViewFileRead | None = None
