"""Store and retrieve artifact blobs through the shared file backend."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.keys import build_artifact_file_key
from app.artifacts.persistence import ArtifactFile, ArtifactFileRole
from app.file_storage.backends.base import StorageBackend
from app.file_storage.factory import get_storage_backend


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


async def store_artifact_file_stream(
    session: AsyncSession,
    *,
    artifact_id: int,
    workspace_id: int,
    role: ArtifactFileRole,
    chunks: AsyncIterable[bytes],
    filename: str,
    mime_type: str,
    expected_sha256: str,
    backend: StorageBackend | None = None,
) -> ArtifactFile:
    """Store and bind a large artifact in one streaming pass."""
    backend = backend or get_storage_backend()
    storage_key = build_artifact_file_key(
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        role=role,
        filename=filename,
    )
    digest = hashlib.sha256()
    size_bytes = 0

    async def hashing_chunks() -> AsyncIterator[bytes]:
        nonlocal size_bytes
        async for chunk in chunks:
            if not chunk:
                continue
            digest.update(chunk)
            size_bytes += len(chunk)
            yield chunk

    try:
        await backend.put_stream(storage_key, hashing_chunks(), content_type=mime_type)
        actual_sha256 = digest.hexdigest()
        if size_bytes == 0:
            raise ValueError(f"Artifact file is empty: {filename}")
        if actual_sha256 != expected_sha256:
            raise ValueError(
                "The artifact changed after verification. Verify it again, then save."
            )
    except BaseException:
        await backend.delete(storage_key)
        raise

    record = ArtifactFile(
        artifact_id=artifact_id,
        role=role,
        storage_backend=backend.backend_name,
        storage_key=storage_key,
        original_filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        checksum_sha256=actual_sha256,
    )
    session.add(record)
    return record


def open_artifact_file_stream(
    record: ArtifactFile, *, backend: StorageBackend | None = None
) -> AsyncIterator[bytes]:
    backend = backend or get_storage_backend(record.storage_backend)
    return backend.open_stream(record.storage_key)


def open_artifact_file_range(
    record: ArtifactFile,
    start: int,
    end: int,
    *,
    backend: StorageBackend | None = None,
) -> AsyncIterator[bytes]:
    backend = backend or get_storage_backend(record.storage_backend)
    return backend.open_range(record.storage_key, start, end)
