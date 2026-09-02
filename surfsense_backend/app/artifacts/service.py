"""Transactional write-through persistence for generated artifacts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.artifacts.persistence import Artifact, ArtifactFile, ArtifactFileRole
from app.artifacts.storage import store_artifact_file, store_artifact_file_stream
from app.db import Document, DocumentStatus, DocumentType, Workspace
from app.file_storage.factory import get_storage_backend
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.paths import allocate_path, to_store_path
from app.knowledge_store.service import record_markdown_files
from app.knowledge_store.settings import knowledge_store_enabled_for
from app.utils.document_converters import (
    generate_content_hash,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArtifactFileInput:
    data: bytes
    filename: str
    mime_type: str
    role: str = "primary"


@dataclass(frozen=True)
class ArtifactFileStreamInput:
    chunks: AsyncIterable[bytes]
    filename: str
    mime_type: str
    expected_sha256: str
    role: str = "primary"


type ArtifactInputFile = ArtifactFileInput | ArtifactFileStreamInput


@dataclass(frozen=True)
class ArtifactSavedFile:
    file_id: int
    role: str
    filename: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True)
class ArtifactSaved:
    status: str
    artifact_id: int
    generation: int
    title: str
    format: str
    files: list[ArtifactSavedFile]


def _validated_files(
    files: list[ArtifactInputFile],
) -> list[tuple[ArtifactInputFile, ArtifactFileRole]]:
    try:
        validated = [(file, ArtifactFileRole(file.role)) for file in files]
    except ValueError:
        raise ValueError("artifact file role must be 'primary' or 'preview'") from None
    roles = [role for _, role in validated]
    if len(roles) != len(set(roles)):
        raise ValueError("an artifact may contain at most one file per role")
    return validated


def _validate_files(files: list[ArtifactInputFile]) -> None:
    """Compatibility validation seam used by focused unit tests."""
    _validated_files(files)


def _revision_metadata(
    current: dict[str, Any] | None,
    extra: dict[str, Any] | None,
    *,
    artifact_format: str,
) -> dict[str, Any]:
    metadata = {**(current or {}), **(extra or {})}
    # Interaction state is generation-scoped and cannot survive any content
    # revision, including a semantic format switch.
    metadata.pop("flashcards", None)
    metadata.pop("quiz", None)
    return metadata


def _artifact_format(
    files: list[tuple[ArtifactInputFile, ArtifactFileRole]],
    *,
    explicit: str | None = None,
) -> str:
    if explicit:
        return str(explicit)
    primary = next(
        (file for file, role in files if role is ArtifactFileRole.PRIMARY), None
    )
    if primary is None:
        return "markdown"
    suffix = Path(primary.filename).suffix.lower().lstrip(".")
    return suffix or primary.mime_type.split("/", 1)[-1]


async def _working_copy_paths(root: Path) -> set[str]:
    def collect() -> set[str]:
        documents = root / "documents"
        if not documents.exists():
            return set()
        return {
            "/" + path.relative_to(root).as_posix()
            for path in documents.rglob("*")
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
    # Both sources: a working copy cannot see a sibling turn's files, and the
    # rows cannot see what this turn has yet to commit. Either alone hands out a
    # taken path and the insert dies on the unique index.
    paths = await session.scalars(
        select(Document.path).where(
            Document.workspace_id == workspace_id,
            Document.path.is_not(None),
        )
    )
    taken = set(paths)
    if working_copy_root is not None:
        taken |= await _working_copy_paths(working_copy_root)

    return allocate_path(
        name=title,
        folder_parts=(),
        taken=taken,
    ).virtual_path


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


async def _delete_blobs_best_effort(blob_refs: list[tuple[str, str]]) -> None:
    for storage_backend, storage_key in blob_refs:
        try:
            await get_storage_backend(storage_backend).delete(storage_key)
        except Exception:
            logger.warning(
                "Failed to delete artifact blob %s",
                storage_key,
                exc_info=True,
            )


async def save_artifact(
    session: AsyncSession,
    *,
    workspace_id: int,
    thread_id: int | None,
    tool_call_id: str | None,
    title: str,
    markdown_representation: str,
    files: list[ArtifactInputFile],
    artifact_id: int | None = None,
    expected_generation: int | None = None,
    extra_metadata: dict[str, Any] | None = None,
    format: str | None = None,
    committed_by_turn: bool = False,
) -> ArtifactSaved:
    """Create or revise an artifact atomically and return its stable identity.

    Set ``committed_by_turn`` when an agent turn will commit the body as part of
    its own revision; the markdown then stages into that turn's working copy.
    Celery tasks and scripts leave it unset and the body is recorded here — the
    default that costs a spare revision rather than losing the body.
    """
    title = title.strip()
    if not title:
        raise ValueError("artifact title must not be empty")
    if not markdown_representation.strip():
        raise ValueError("artifact content must not be empty")
    validated_files = _validated_files(files)
    artifact_format = _artifact_format(validated_files, explicit=format)

    git_native = await knowledge_store_enabled_for(workspace_id)
    working_copy_root: Path | None = None
    if git_native and committed_by_turn:
        working_copy_root = (
            await KnowledgeStore.for_workspace(workspace_id).open_turn_copy(thread_id)
        ).path

    old_files: list[ArtifactFile] = []
    now = datetime.now(UTC)
    if artifact_id is None:
        if expected_generation is not None:
            raise ValueError(
                "expected_generation is only valid when revising an artifact"
            )
        path = await _allocate_artifact_path(
            session,
            workspace_id=workspace_id,
            title=title,
            working_copy_root=working_copy_root,
        )
        created_by_id = await session.scalar(
            select(Workspace.user_id).where(Workspace.id == workspace_id)
        )
        if created_by_id is None:
            raise ValueError("workspace does not exist")
        document = Document(
            title=title,
            document_type=DocumentType.ARTIFACT,
            document_metadata={},
            path=path,
            content=markdown_representation,
            source_markdown=markdown_representation,
            content_hash=generate_content_hash(markdown_representation, workspace_id),
            unique_identifier_hash=generate_unique_identifier_hash(
                DocumentType.NOTE, path, workspace_id
            ),
            workspace_id=workspace_id,
            folder_id=None,
            created_by_id=created_by_id,
            status=DocumentStatus.pending(),
            updated_at=now,
        )
        session.add(document)
        await session.flush()
        artifact = Artifact(
            document_id=document.id,
            workspace_id=workspace_id,
            thread_id=thread_id,
            created_by_id=created_by_id,
            format=artifact_format,
            generation=1,
            created_by_tool_call_id=tool_call_id,
            updated_by_tool_call_id=tool_call_id,
            artifact_metadata=extra_metadata,
            updated_at=now,
        )
        session.add(artifact)
        await session.flush()
    else:
        artifact = await session.scalar(
            select(Artifact)
            .options(
                selectinload(Artifact.document),
                selectinload(Artifact.files),
            )
            .where(
                Artifact.id == artifact_id,
                Artifact.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        if artifact is None:
            raise ValueError("artifact does not exist in this workspace")
        if expected_generation is None:
            raise ValueError(
                "expected_generation is required when revising an artifact"
            )
        if artifact.generation != expected_generation:
            raise ValueError(
                "artifact was revised by another operation; refresh the artifact "
                "roster and load the latest revision workspace"
            )
        document = artifact.document
        old_files = list(artifact.files)
        artifact.format = artifact_format
        artifact.generation += 1
        if tool_call_id is not None:
            artifact.updated_by_tool_call_id = tool_call_id
        artifact.artifact_metadata = _revision_metadata(
            artifact.artifact_metadata,
            extra_metadata,
            artifact_format=artifact_format,
        )
        artifact.updated_at = now
        document.title = title
        document.content = markdown_representation
        document.source_markdown = markdown_representation
        document.content_hash = generate_content_hash(
            markdown_representation, workspace_id
        )
        document.document_metadata = {
            **(document.document_metadata or {}),
            "artifact_id": artifact.id,
        }
        document.status = DocumentStatus.pending()
        document.updated_at = now
        if old_files:
            await session.execute(
                delete(ArtifactFile).where(
                    ArtifactFile.id.in_([file.id for file in old_files])
                )
            )

    document.document_metadata = {
        **(document.document_metadata or {}),
        "artifact_id": artifact.id,
    }
    old_blob_refs = [(file.storage_backend, file.storage_key) for file in old_files]

    backend = get_storage_backend()
    new_records: list[ArtifactFile] = []
    new_blob_refs: list[tuple[str, str]] = []
    working_copy_state: tuple[Path, bytes | None] | None = None
    try:
        for file, role in validated_files:
            if isinstance(file, ArtifactFileStreamInput):
                record = await store_artifact_file_stream(
                    session,
                    artifact_id=artifact.id,
                    workspace_id=workspace_id,
                    role=role,
                    chunks=file.chunks,
                    filename=file.filename,
                    mime_type=file.mime_type,
                    expected_sha256=file.expected_sha256,
                    backend=backend,
                )
            else:
                record = await store_artifact_file(
                    session,
                    artifact_id=artifact.id,
                    workspace_id=workspace_id,
                    role=role,
                    data=file.data,
                    filename=file.filename,
                    mime_type=file.mime_type,
                    backend=backend,
                )
            new_records.append(record)
            new_blob_refs.append((record.storage_backend, record.storage_key))
        await session.flush()
        saved_result = ArtifactSaved(
            status="saved",
            artifact_id=artifact.id,
            generation=artifact.generation,
            title=document.title,
            format=artifact.format,
            files=[
                ArtifactSavedFile(
                    file_id=record.id,
                    role=record.role.value,
                    filename=record.original_filename,
                    mime_type=record.mime_type or "application/octet-stream",
                    size_bytes=record.size_bytes,
                )
                for record in new_records
            ],
        )
        if working_copy_root is not None:
            working_copy_state = await _write_working_copy(
                working_copy_root, document.path, markdown_representation
            )
        elif not git_native:
            connector_document = ConnectorDocument(
                title=document.title,
                source_markdown=markdown_representation,
                unique_id=document.path,
                document_type=DocumentType.ARTIFACT,
                workspace_id=workspace_id,
                metadata=document.document_metadata or {},
                created_by_id=str(document.created_by_id),
                folder_id=document.folder_id,
            )
            await IndexingPipelineService(session).index(document, connector_document)
        await session.commit()
    except Exception:
        await session.rollback()
        if working_copy_state is not None:
            await _restore_working_copy(*working_copy_state)
        await _delete_blobs_best_effort(new_blob_refs)
        raise

    if git_native and working_copy_root is None:
        await _record_body(
            workspace_id=workspace_id,
            path=document.path,
            markdown=markdown_representation,
            title=document.title,
            author_user_id=str(document.created_by_id),
        )

    await _delete_blobs_best_effort(old_blob_refs)
    return saved_result


async def _record_body(
    *,
    workspace_id: int,
    path: str,
    markdown: str,
    title: str,
    author_user_id: str,
) -> None:
    """Record the body of an artifact no turn will commit.

    Must run after the rows commit: a revision left behind by a rolled-back
    write is adopted as a stray note. The reverse gap is self-healing, since
    re-recording identical content is a no-op, so failure warns rather than
    raising over an artifact the caller has already been handed.
    """
    try:
        await record_markdown_files(
            workspace_id=workspace_id,
            files={to_store_path(path): markdown},
            message=f"artifacts: save {title}",
            author_user_id=author_user_id,
        )
    except Exception:
        logger.warning(
            "Could not record artifact body for workspace %s at %s",
            workspace_id,
            path,
            exc_info=True,
        )


async def persist_artifact(session: AsyncSession, input: Any) -> ArtifactSaved:
    """Media/tool shim: ``ArtifactInput`` → document-backed ``save_artifact``."""
    from app.artifacts.schemas import ArtifactInput

    if not isinstance(input, ArtifactInput):
        raise TypeError("persist_artifact expects ArtifactInput")
    files = [
        ArtifactFileInput(
            data=file.data,
            filename=file.filename,
            mime_type=file.mime_type,
            role=file.role.value if hasattr(file.role, "value") else str(file.role),
        )
        for file in input.files
    ]
    return await save_artifact(
        session,
        workspace_id=input.workspace_id,
        thread_id=input.thread_id,
        tool_call_id=input.tool_call_id,
        title=input.title,
        markdown_representation=input.markdown_representation,
        files=files,
        artifact_id=input.artifact_id,
        expected_generation=input.expected_generation,
        extra_metadata=input.metadata,
        format=str(input.format) if input.format is not None else None,
    )
