"""Create or revise artifacts via ArtifactInput → persist_artifact."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.artifacts.indexing import index_artifact
from app.artifacts.persistence import (
    Artifact,
    ArtifactFile,
    ArtifactFileRole,
    ArtifactFormat,
)
from app.artifacts.schemas import (
    ArtifactFileInput,
    ArtifactInput,
    ArtifactSaved,
    ArtifactSavedFile,
)
from app.artifacts.storage import store_artifact_file
from app.file_storage.factory import get_storage_backend
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.paths.naming import normalize_filename
from app.knowledge_store.settings import knowledge_store_enabled_for

logger = logging.getLogger(__name__)


def _validated_files(
    files: tuple[ArtifactFileInput, ...] | list[ArtifactFileInput],
) -> list[tuple[ArtifactFileInput, ArtifactFileRole]]:
    validated: list[tuple[ArtifactFileInput, ArtifactFileRole]] = []
    for file in files:
        role = file.role
        if not isinstance(role, ArtifactFileRole):
            try:
                role = ArtifactFileRole(role)
            except ValueError:
                raise ValueError(
                    "artifact file role must be 'primary', 'preview', or 'source'"
                ) from None
        validated.append((file, role))
    roles = [role for _, role in validated]
    if len(roles) != len(set(roles)):
        raise ValueError("an artifact may contain at most one file per role")
    return validated


def _validate_files(files: list[ArtifactFileInput]) -> None:
    """Compatibility validation seam used by focused unit tests."""
    _validated_files(files)


def _artifact_format(
    files: list[tuple[ArtifactFileInput, ArtifactFileRole]],
    *,
    explicit: ArtifactFormat | str | None = None,
) -> str:
    if explicit:
        return str(explicit)
    primary = next(
        (file for file, role in files if role is ArtifactFileRole.PRIMARY), None
    )
    if primary is None:
        return ArtifactFormat.MARKDOWN.value
    suffix = Path(primary.filename).suffix.lower().lstrip(".")
    return suffix or primary.mime_type.split("/", 1)[-1]


def _markdown_hash(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


async def _working_copy_paths(root: Path) -> set[str]:
    def collect() -> set[str]:
        artifacts = root / "artifacts"
        if not artifacts.exists():
            return set()
        return {
            "/" + path.relative_to(root).as_posix()
            for path in artifacts.rglob("*")
            if path.is_file()
        }

    return await asyncio.to_thread(collect)


async def _allocate_artifact_path(
    session: AsyncSession,
    *,
    workspace_id: int,
    title: str,
    working_copy_root: Path | None,
) -> str:
    paths = await session.scalars(
        select(Artifact.path).where(Artifact.workspace_id == workspace_id)
    )
    taken = set(paths)
    if working_copy_root is not None:
        taken.update(await _working_copy_paths(working_copy_root))

    filename = normalize_filename(title)
    if not filename.lower().endswith(".md"):
        filename = f"{filename}.md"
    candidate = f"/artifacts/{filename}"
    if candidate not in taken:
        return candidate

    stem, dot, extension = filename.rpartition(".")
    base, suffix = (stem, f".{extension}") if dot else (filename, "")
    counter = 2
    while f"/artifacts/{base} ({counter}){suffix}" in taken:
        counter += 1
    return f"/artifacts/{base} ({counter}){suffix}"


async def _write_working_copy(
    root: Path, path: str, markdown: str
) -> tuple[Path, bytes | None]:
    target = root / path.removeprefix("/")

    def write() -> tuple[Path, bytes | None]:
        previous = target.read_bytes() if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        return target, previous

    return await asyncio.to_thread(write)


async def _restore_working_copy(target: Path, previous: bytes | None) -> None:
    def restore() -> None:
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(previous)

    await asyncio.to_thread(restore)


async def _delete_blobs_best_effort(records: list[ArtifactFile]) -> None:
    for record in records:
        try:
            await get_storage_backend(record.storage_backend).delete(record.storage_key)
        except Exception:
            logger.warning(
                "Failed to delete artifact blob %s",
                record.storage_key,
                exc_info=True,
            )


async def persist_artifact(
    session: AsyncSession,
    input: ArtifactInput,
) -> ArtifactSaved:
    """Create or revise an artifact from a normalized ArtifactInput."""
    title = input.title.strip()
    if not title:
        raise ValueError("artifact title must not be empty")
    if not input.markdown_representation.strip():
        raise ValueError("artifact content must not be empty")
    validated_files = _validated_files(input.files)
    artifact_format = _artifact_format(validated_files, explicit=input.format)

    working_copy_root: Path | None = None
    if await knowledge_store_enabled_for(input.workspace_id):
        working_copy_root = (
            await KnowledgeStore.for_workspace(input.workspace_id).open_turn_copy(
                input.thread_id
            )
        ).path

    old_files: list[ArtifactFile] = []
    now = datetime.now(UTC)
    if input.artifact_id is None:
        if input.expected_version is not None:
            raise ValueError(
                "expected_version is only valid when revising an artifact"
            )
        path = await _allocate_artifact_path(
            session,
            workspace_id=input.workspace_id,
            title=title,
            working_copy_root=working_copy_root,
        )
        artifact = Artifact(
            workspace_id=input.workspace_id,
            thread_id=input.thread_id,
            created_by_id=input.created_by_id,
            title=title,
            format=artifact_format,
            markdown_representation=input.markdown_representation,
            path=path,
            markdown_hash=_markdown_hash(input.markdown_representation),
            version=1,
            indexing_status="pending",
            created_by_tool_call_id=input.tool_call_id,
            updated_by_tool_call_id=input.tool_call_id,
            artifact_metadata=input.metadata,
            updated_at=now,
        )
        session.add(artifact)
        await session.flush()
    else:
        artifact = await session.scalar(
            select(Artifact)
            .options(selectinload(Artifact.files))
            .where(
                Artifact.id == input.artifact_id,
                Artifact.workspace_id == input.workspace_id,
            )
            .with_for_update()
        )
        if artifact is None:
            raise ValueError("artifact does not exist in this workspace")
        if input.expected_version is None:
            raise ValueError(
                "expected_version is required when revising an artifact"
            )
        if artifact.version != input.expected_version:
            raise ValueError(
                "artifact was revised by another operation; load its source again"
            )
        old_files = list(artifact.files)
        artifact.title = title
        artifact.format = artifact_format
        artifact.markdown_representation = input.markdown_representation
        artifact.markdown_hash = _markdown_hash(input.markdown_representation)
        artifact.version += 1
        artifact.indexing_status = "pending"
        artifact.indexing_error = None
        if input.tool_call_id is not None:
            artifact.updated_by_tool_call_id = input.tool_call_id
        if input.created_by_id is not None and artifact.created_by_id is None:
            artifact.created_by_id = input.created_by_id
        artifact.artifact_metadata = {
            **(artifact.artifact_metadata or {}),
            **(input.metadata or {}),
        }
        artifact.updated_at = now
        if old_files:
            await session.execute(
                delete(ArtifactFile).where(
                    ArtifactFile.id.in_([file.id for file in old_files])
                )
            )

    backend = get_storage_backend()
    new_records: list[ArtifactFile] = []
    working_copy_state: tuple[Path, bytes | None] | None = None
    try:
        for file, role in validated_files:
            record = await store_artifact_file(
                session,
                artifact_id=artifact.id,
                workspace_id=input.workspace_id,
                role=role,
                data=file.data,
                filename=file.filename,
                mime_type=file.mime_type,
                backend=backend,
            )
            new_records.append(record)
        await session.flush()
        if working_copy_root is not None:
            working_copy_state = await _write_working_copy(
                working_copy_root, artifact.path, input.markdown_representation
            )
        else:
            await index_artifact(
                session,
                artifact=artifact,
                markdown=input.markdown_representation,
            )
            await session.flush()
        await session.commit()
    except Exception:
        await session.rollback()
        if working_copy_state is not None:
            await _restore_working_copy(*working_copy_state)
        await _delete_blobs_best_effort(new_records)
        raise

    await _delete_blobs_best_effort(old_files)
    return ArtifactSaved(
        status="saved",
        artifact_id=artifact.id,
        version=artifact.version,
        title=artifact.title,
        path=artifact.path,
        files=[
            ArtifactSavedFile(
                file_id=record.id,
                role=record.role,
                filename=record.original_filename,
                mime_type=record.mime_type or "application/octet-stream",
                size_bytes=record.size_bytes,
            )
            for record in new_records
            if record.role is not ArtifactFileRole.SOURCE
        ],
    )


async def save_artifact(
    session: AsyncSession,
    *,
    workspace_id: int,
    thread_id: int | None,
    tool_call_id: str,
    title: str,
    markdown_representation: str,
    files: list[ArtifactFileInput],
    artifact_id: int | None = None,
    expected_version: int | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> ArtifactSaved:
    """Office/tool convenience: build ArtifactInput then persist."""
    return await persist_artifact(
        session,
        ArtifactInput(
            workspace_id=workspace_id,
            title=title,
            markdown_representation=markdown_representation,
            tool_call_id=tool_call_id,
            files=tuple(files),
            thread_id=thread_id,
            artifact_id=artifact_id,
            expected_version=expected_version,
            metadata=extra_metadata,
        ),
    )
