"""Find an Artifact already written for a legacy media row."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.persistence import Artifact


async def existing_legacy_artifact(
    session: AsyncSession,
    *,
    workspace_id: int,
    kind: str,
    legacy_id: int,
) -> Artifact | None:
    result = await session.execute(
        select(Artifact)
        .where(
            Artifact.workspace_id == workspace_id,
            Artifact.format == kind,
        )
        .order_by(Artifact.id.desc())
    )
    for artifact in result.scalars():
        legacy = (artifact.artifact_metadata or {}).get("legacy") or {}
        if legacy.get("kind") == kind and legacy.get("id") == legacy_id:
            return artifact
    return None


def legacy_metadata(
    kind: str, legacy_id: int, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    meta: dict[str, Any] = {"legacy": {"kind": kind, "id": legacy_id}}
    if extra:
        meta.update(extra)
    return meta
