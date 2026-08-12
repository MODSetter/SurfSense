"""Store and retrieve artifact blobs through the shared file backend."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import AsyncIterator, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.keys import build_artifact_file_key
from app.artifacts.persistence import ArtifactFile, ArtifactFileRole
from app.file_storage.backends.base import StorageBackend
from app.file_storage.factory import get_storage_backend

logger = logging.getLogger(__name__)


async def store_artifact_file(
    session: AsyncSession,
    *,
    artifact_id: int,
    workspace_id: int,
    role: ArtifactFileRole,
    data: bytes,
    filename: str,
    mime_type: str,
    backend: StorageBackend | None = None,
) -> ArtifactFile:
    """Write immutable bytes and add their metadata row to ``session``."""
    backend = backend or get_storage_backend()
    storage_key = build_artifact_file_key(
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        role=role,
        filename=filename,
    )
    await backend.put(storage_key, data, content_type=mime_type)

    record = ArtifactFile(
        artifact_id=artifact_id,
        role=role,
        storage_backend=backend.backend_name,
        storage_key=storage_key,
        original_filename=filename,
        mime_type=mime_type,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )
    session.add(record)
    return record


def open_artifact_file_stream(
    record: ArtifactFile, *, backend: StorageBackend | None = None
) -> AsyncIterator[bytes]:
    backend = backend or get_storage_backend(record.storage_backend)
    return backend.open_stream(record.storage_key)


async def purge_artifact_blobs(
    session: AsyncSession,
    *,
    artifact_ids: Sequence[int],
    backend: StorageBackend | None = None,
) -> None:
    """Best-effort delete all blobs belonging to the supplied artifacts."""
    if not artifact_ids:
        return

    result = await session.execute(
        select(ArtifactFile.storage_backend, ArtifactFile.storage_key).where(
            ArtifactFile.artifact_id.in_(artifact_ids)
        )
    )
    for backend_name, storage_key in result.all():
        try:
            selected_backend = backend or get_storage_backend(backend_name)
            await selected_backend.delete(storage_key)
        except Exception as delete_error:
            logger.warning(
                "Failed to delete artifact blob %s: %s",
                storage_key,
                delete_error,
            )


async def purge_artifact_file_records(records: Sequence[ArtifactFile]) -> None:
    """Best-effort purge already-loaded records after their DB rows commit."""
    for record in records:
        try:
            await get_storage_backend(record.storage_backend).delete(record.storage_key)
        except Exception as delete_error:
            logger.warning(
                "Failed to delete artifact blob %s: %s",
                record.storage_key,
                delete_error,
            )
