"""Write-through persistence for generated artifacts."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Document, DocumentStatus, DocumentType
from app.file_storage.factory import get_storage_backend
from app.file_storage.persistence.enums import DocumentFileKind
from app.file_storage.persistence.models import DocumentFile
from app.file_storage.service import store_document_file
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.paths import StorePath, allocate_path
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
class ArtifactSavedFile:
    file_id: int
    role: str
    filename: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True)
class ArtifactSaved:
    status: str
    document_id: int
    title: str
    files: list[ArtifactSavedFile]


def _validate_files(files: list[ArtifactFileInput]) -> None:
    roles = [file.role for file in files]
    if any(role not in {"primary", "preview", "source"} for role in roles):
        raise ValueError("artifact file role must be 'primary', 'preview', or 'source'")
    if len(roles) != len(set(roles)):
        raise ValueError("an artifact may contain at most one file per role")


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
) -> StorePath:
    paths = await session.scalars(
        select(Document.path).where(
            Document.workspace_id == workspace_id,
            Document.path.is_not(None),
        )
    )
    taken = set(paths)
    if working_copy_root is not None:
        taken.update(await _working_copy_paths(working_copy_root))

    while True:
        path = allocate_path(name=title, folder_parts=(), taken=taken)
        path_hash = generate_unique_identifier_hash(
            DocumentType.NOTE, path.virtual_path, workspace_id
        )
        collision = await session.scalar(
            select(Document.id).where(Document.unique_identifier_hash == path_hash)
        )
        if collision is None:
            return path


def _path_for_revision(document: Document) -> StorePath:
    if document.path:
        return StorePath.from_virtual(document.path)
    raise ValueError("artifact path has not been recorded yet")


async def _write_working_copy(
    root: Path, path: StorePath, markdown: str
) -> tuple[Path, bytes | None]:
    target = root / path.store_path

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


async def _delete_blobs_best_effort(records: list[DocumentFile]) -> None:
    for record in records:
        try:
            await get_storage_backend(record.storage_backend).delete(record.storage_key)
        except Exception:
            logger.warning(
                "Failed to delete replaced artifact blob %s",
                record.storage_key,
                exc_info=True,
            )


async def _index_legacy(
    session: AsyncSession,
    *,
    document: Document,
    path: StorePath,
    markdown: str,
) -> None:
    indexed = await IndexingPipelineService(session).index(
        document,
        ConnectorDocument(
            title=document.title,
            source_markdown=markdown,
            unique_id=path.virtual_path,
            document_type=DocumentType.NOTE,
            workspace_id=document.workspace_id,
            created_by_id=str(document.created_by_id or "artifact-agent"),
            metadata=document.document_metadata or {},
            folder_id=document.folder_id,
        ),
    )
    if not DocumentStatus.is_state(indexed.status, DocumentStatus.READY):
        raise RuntimeError(
            (indexed.status or {}).get("reason") or "artifact indexing failed"
        )


async def save_artifact(
    session: AsyncSession,
    *,
    workspace_id: int,
    thread_id: int | str | None,
    tool_call_id: str,
    title: str,
    markdown_representation: str,
    files: list[ArtifactFileInput],
    document_id: int | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> ArtifactSaved:
    """Create or replace an artifact and make it durable before returning."""
    title = title.strip()
    if not title:
        raise ValueError("artifact title must not be empty")
    if not markdown_representation.strip():
        raise ValueError("artifact content must not be empty")
    _validate_files(files)

    git_native = await knowledge_store_enabled_for(workspace_id)
    working_copy_root: Path | None = None
    if git_native:
        working_copy_root = (
            await KnowledgeStore.for_workspace(workspace_id).open_turn_copy(thread_id)
        ).path

    old_files: list[DocumentFile] = []
    if document_id is None:
        path = await _allocate_artifact_path(
            session,
            workspace_id=workspace_id,
            title=title,
            working_copy_root=working_copy_root,
        )
        document = Document(
            title=title,
            document_type=DocumentType.NOTE,
            document_metadata={
                **(extra_metadata or {}),
                "generated": True,
                "thread_id": thread_id,
                "tool_call_id": tool_call_id,
            },
            path=path.virtual_path,
            content=markdown_representation,
            content_hash=generate_content_hash(markdown_representation, workspace_id),
            unique_identifier_hash=generate_unique_identifier_hash(
                DocumentType.NOTE, path.virtual_path, workspace_id
            ),
            source_markdown=markdown_representation,
            workspace_id=workspace_id,
            status=DocumentStatus.ready(),
            updated_at=datetime.now(UTC),
        )
        session.add(document)
        await session.flush()
    else:
        document = await session.scalar(
            select(Document)
            .options(selectinload(Document.files))
            .where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
            )
        )
        if document is None or not (document.document_metadata or {}).get("generated"):
            raise ValueError("artifact does not exist in this workspace")
        path = _path_for_revision(document)
        old_files = list(document.files)
        document.title = title
        document.content = markdown_representation
        document.content_hash = generate_content_hash(
            markdown_representation, workspace_id
        )
        document.source_markdown = markdown_representation
        document.document_metadata = {
            **(document.document_metadata or {}),
            **(extra_metadata or {}),
            "generated": True,
            "thread_id": thread_id,
            "tool_call_id": tool_call_id,
        }
        document.updated_at = datetime.now(UTC)
        for old_file in old_files:
            await session.delete(old_file)

    backend = get_storage_backend()
    new_records: list[DocumentFile] = []
    working_copy_state: tuple[Path, bytes | None] | None = None
    try:
        for file in files:
            record = await store_document_file(
                session,
                document_id=document.id,
                workspace_id=workspace_id,
                data=file.data,
                filename=file.filename,
                mime_type=file.mime_type,
                kind=DocumentFileKind.GENERATED,
                role=file.role,
                backend=backend,
            )
            new_records.append(record)
        await session.flush()

        if working_copy_root is not None:
            working_copy_state = await _write_working_copy(
                working_copy_root, path, markdown_representation
            )
        await session.commit()
    except Exception:
        await session.rollback()
        if working_copy_state is not None:
            await _restore_working_copy(*working_copy_state)
        await _delete_blobs_best_effort(new_records)
        raise

    await _delete_blobs_best_effort(old_files)

    if not git_native:
        await _index_legacy(
            session,
            document=document,
            path=path,
            markdown=markdown_representation,
        )

    return ArtifactSaved(
        status="saved",
        document_id=document.id,
        title=document.title,
        files=[
            ArtifactSavedFile(
                file_id=record.id,
                role=record.role,
                filename=record.original_filename,
                mime_type=record.mime_type or "application/octet-stream",
                size_bytes=record.size_bytes,
            )
            for record in new_records
            if record.role != "source"
        ],
    )
