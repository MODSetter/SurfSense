"""Object-key construction for stored document files."""

from __future__ import annotations

import os
import uuid

from app.file_storage.persistence.enums import DocumentFileKind


def build_document_file_key(
    *,
    search_space_id: int,
    document_id: int,
    kind: DocumentFileKind,
    filename: str,
) -> str:
    """Build the storage key for one document file.

    Shape: ``documents/{search_space_id}/{document_id}/{kind}/{uuid}{ext}``.
    """
    extension = os.path.splitext(filename)[1].lower()
    unique = uuid.uuid4().hex
    return (
        f"documents/{search_space_id}/{document_id}/"
        f"{kind.value.lower()}/{unique}{extension}"
    )
