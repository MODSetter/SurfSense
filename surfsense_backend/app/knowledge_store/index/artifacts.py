"""Artifact rows derived from the knowledge store's ``/artifacts`` tree."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.persistence import Artifact
from app.artifacts.storage import purge_artifact_blobs

ARTIFACTS_ROOT = "/artifacts"
ARTIFACTS_STORE_ROOT = "artifacts"


def is_artifact_store_path(path: str) -> bool:
    normalized = path.strip("/")
    return normalized.startswith(f"{ARTIFACTS_STORE_ROOT}/")


def to_artifact_virtual_path(path: str) -> str:
    normalized = path.strip("/")
    if not is_artifact_store_path(normalized):
        raise ValueError(f"Not an artifacts/ path: {path!r}")
    return f"/{normalized}"


async def load_artifacts(
    session: AsyncSession, workspace_id: int
) -> dict[str, Artifact]:
    rows = await session.scalars(
        select(Artifact).where(Artifact.workspace_id == workspace_id)
    )
    return {artifact.path: artifact for artifact in rows}


def follow_artifact_rename(
    owned: dict[str, Artifact], from_path: str, to_path: str
) -> None:
    artifact = owned.pop(from_path, None)
    if artifact is None:
        return
    artifact.path = to_path
    owned[to_path] = artifact


async def upsert_artifact(
    session: AsyncSession,
    *,
    workspace_id: int,
    virtual_path: str,
    content: str,
    owned: dict[str, Artifact],
) -> tuple[Artifact, bool]:
    """Upsert one artifact path without creating a ``Document`` shadow."""
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    artifact = owned.get(virtual_path)
    created = artifact is None
    if artifact is None:
        name = PurePosixPath(virtual_path).name
        artifact = Artifact(
            workspace_id=workspace_id,
            title=name.removesuffix(".md") or name,
            format="markdown",
            search_content=content,
            path=virtual_path,
            content_hash=content_hash,
            generation=1,
            indexing_status="pending",
            updated_at=datetime.now(UTC),
        )
        session.add(artifact)
    elif artifact.content_hash != content_hash:
        # The artifact service has already advanced the generation for its own
        # working-copy write. Direct filesystem edits reach this branch instead.
        artifact.search_content = content
        artifact.content_hash = content_hash
        artifact.generation += 1
        artifact.indexing_status = "pending"
        artifact.indexing_error = None
        artifact.updated_at = datetime.now(UTC)

    await session.flush()
    owned[virtual_path] = artifact
    return artifact, created


async def delete_artifact(
    session: AsyncSession,
    *,
    workspace_id: int,
    virtual_path: str,
    owned: dict[str, Artifact],
) -> Artifact | None:
    artifact = owned.get(virtual_path)
    if artifact is None:
        artifact = await session.scalar(
            select(Artifact).where(
                Artifact.workspace_id == workspace_id,
                Artifact.path == virtual_path,
            )
        )
    if artifact is None:
        return None
    await purge_artifact_blobs(session, artifact_ids=[artifact.id])
    owned.pop(virtual_path, None)
    await session.delete(artifact)
    return artifact


async def prune_artifacts(
    session: AsyncSession,
    *,
    workspace_id: int,
    owned: dict[str, Artifact],
    live: set[str],
) -> int:
    deleted = 0
    for virtual_path in list(owned):
        if virtual_path in live:
            continue
        if await delete_artifact(
            session,
            workspace_id=workspace_id,
            virtual_path=virtual_path,
            owned=owned,
        ):
            deleted += 1
    return deleted
