"""Application service: persist, locate, and remove a document's stored files.

Coordinates the storage backend (bytes) with the ``document_files`` table
(metadata). Callers own the surrounding DB transaction/commit.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import AsyncIterator, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.file_storage.backends.base import StorageBackend
from app.file_storage.factory import get_storage_backend
from app.file_storage.keys import build_document_file_key
from app.file_storage.persistence.enums import DocumentFileKind
from app.file_storage.persistence.models import DocumentFile

logger = logging.getLogger(__name__)


async def store_document_file(
    session: AsyncSession,
    *,
    document_id: int,
    workspace_id: int,
    data: bytes,
    filename: str,
    mime_type: str | None = None,
    kind: DocumentFileKind = DocumentFileKind.ORIGINAL,
    created_by_id: str | UUID | None = None,
    backend: StorageBackend | None = None,
) -> DocumentFile:
    """Write bytes to storage and add a ``DocumentFile`` row to the session."""
    backend = backend or get_storage_backend()
    key = build_document_file_key(
        workspace_id=workspace_id,
        document_id=document_id,
        kind=kind,
        filename=filename,
    )
    await backend.put(key, data, content_type=mime_type)

    record = DocumentFile(
        document_id=document_id,
        workspace_id=workspace_id,
        kind=kind,
        storage_backend=backend.backend_name,
        storage_key=key,
        original_filename=filename,
        mime_type=mime_type,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
        created_by_id=created_by_id,
    )
    session.add(record)
    return record


async def list_document_files(
    session: AsyncSession, *, document_id: int
) -> list[DocumentFile]:
    """Return all stored files for a document, newest first."""
    result = await session.execute(
        select(DocumentFile)
        .where(DocumentFile.document_id == document_id)
        .order_by(DocumentFile.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document_file(
    session: AsyncSession,
    *,
    document_id: int,
    kind: DocumentFileKind = DocumentFileKind.ORIGINAL,
) -> DocumentFile | None:
    """Return the most recent stored file of ``kind`` for a document."""
    result = await session.execute(
        select(DocumentFile)
        .where(
            DocumentFile.document_id == document_id,
            DocumentFile.kind == kind,
        )
        .order_by(DocumentFile.created_at.desc())
    )
    return result.scalars().first()


def open_document_file_stream(
    record: DocumentFile, *, backend: StorageBackend | None = None
) -> AsyncIterator[bytes]:
    """Open a chunked byte stream for a stored file."""
    backend = backend or get_storage_backend()
    return backend.open_stream(record.storage_key)


async def purge_document_blobs(
    session: AsyncSession,
    *,
    document_ids: Sequence[int],
    backend: StorageBackend | None = None,
) -> None:
    """Delete stored blobs for the given documents.

    Call this before the ``document_files`` rows are removed (they cascade with
    the document). Best-effort: a failed blob delete is logged, not raised, so
    document deletion is never blocked by an orphaned blob.
    """
    if not document_ids:
        return

    backend = backend or get_storage_backend()
    result = await session.execute(
        select(DocumentFile.storage_key).where(
            DocumentFile.document_id.in_(document_ids)
        )
    )
    for storage_key in result.scalars().all():
        try:
            await backend.delete(storage_key)
        except Exception as delete_error:
            logger.warning(
                "Failed to delete stored blob %s: %s", storage_key, delete_error
            )
