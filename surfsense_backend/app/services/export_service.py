"""Service for exporting knowledge base content as a ZIP archive."""

import asyncio
import json
import logging
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import (
    ARTIFACT_API_SOURCE,
    Chunk,
    Document,
    DocumentType,
    Folder,
    NewChatMessageRole,
    NewChatThread,
    Workspace,
    WorkspaceMembership,
)
from app.services.folder_service import get_folder_subtree_ids
from app.services.okf import (
    INDEX_FILENAME,
    LOG_FILENAME,
    ConceptRef,
    LogEntry,
    SubdirRef,
    document_to_concept,
    folder_to_index,
    folder_to_log,
    okf_type,
)
from app.utils.content_utils import extract_text_content

logger = logging.getLogger(__name__)

# Root index.md declares the targeted OKF version in frontmatter - the one place
# the spec permits frontmatter in an index file.
_ROOT_INDEX_FRONTMATTER = '---\nokf_version: "0.1"\n---\n\n'

_RESERVED_STEMS = {"index", "log"}
_ACCOUNT_FORMAT = "surfsense-export/1"
_SKIP_REASONS = frozenset({"pending", "processing", "empty"})
_CITATION_RE = re.compile(r"\[citation:\s*([^\]]+?)\s*\]")
_CHAT_ROLES = frozenset({"user", "assistant"})


def _sanitize_filename(title: str) -> str:
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in title).strip()
    return safe[:80] or "document"


def flatten_message_text(
    text: str, title_by_payload: dict[str, str]
) -> tuple[str, list[dict[str, str]]]:
    """Strip ``[citation:…]`` markers and collect distinct titles in first-seen order."""
    citations: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in _CITATION_RE.findall(text):
        title = title_by_payload.get(raw.strip())
        if not title or title in seen:
            continue
        seen.add(title)
        citations.append({"title": title})
    return _CITATION_RE.sub("", text), citations


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _document_source(document: Document) -> str:
    dtype = document.document_type
    return dtype.value if isinstance(dtype, DocumentType) else str(dtype)


def _join_zip_path(prefix: str, rel: str) -> str:
    if not prefix:
        return rel
    return f"{prefix}/{rel}" if rel else prefix


def _doc_state(document: Document) -> str:
    status = document.status or {}
    if not isinstance(status, dict):
        return "ready"
    return status.get("state") or "ready"


def _build_folder_path_map(folders: list[Folder]) -> dict[int, str]:
    """Build a mapping of folder_id -> full path string (e.g. 'Research/AI')."""
    id_to_folder = {f.id: f for f in folders}
    cache: dict[int, str] = {}

    def resolve(folder_id: int) -> str:
        if folder_id in cache:
            return cache[folder_id]
        folder = id_to_folder[folder_id]
        safe_name = _sanitize_filename(folder.name)
        if folder.parent_id is None or folder.parent_id not in id_to_folder:
            cache[folder_id] = safe_name
        else:
            cache[folder_id] = f"{resolve(folder.parent_id)}/{safe_name}"
        return cache[folder_id]

    for f in folders:
        resolve(f.id)

    return cache


async def resolve_document_markdown(
    session: AsyncSession, document: Document
) -> str | None:
    """Resolve markdown content using the 3-tier fallback:
    1. source_markdown  2. blocknote_document conversion  3. chunk concatenation
    """
    if document.source_markdown is not None:
        return document.source_markdown

    if document.blocknote_document:
        from app.utils.blocknote_to_markdown import blocknote_to_markdown

        md = blocknote_to_markdown(document.blocknote_document)
        if md:
            return md

    chunk_result = await session.execute(
        select(Chunk.content)
        .filter(Chunk.document_id == document.id)
        .order_by(Chunk.position, Chunk.id)
    )
    chunks = chunk_result.scalars().all()
    if chunks:
        return "\n\n".join(chunks)

    return None


def _build_index_files(
    dir_concepts: dict[str, list[ConceptRef]],
) -> list[tuple[str, str]]:
    """Build ``index.md`` files for every directory (and ancestor) with content.

    Produces OKF progressive-disclosure listings: each directory lists its
    concepts (grouped by type) and its immediate subdirectories. The bundle-root
    index also declares ``okf_version``.
    """
    all_dirs: set[str] = {""}
    for dir_path in dir_concepts:
        all_dirs.add(dir_path)
        parts = dir_path.split("/") if dir_path else []
        for i in range(1, len(parts)):
            all_dirs.add("/".join(parts[:i]))

    children_by_dir: dict[str, list[str]] = {}
    for dir_path in all_dirs:
        if not dir_path:
            continue
        parent = dir_path.rsplit("/", 1)[0] if "/" in dir_path else ""
        children_by_dir.setdefault(parent, []).append(dir_path)

    index_files: list[tuple[str, str]] = []
    for dir_path in all_dirs:
        subdirs = [
            SubdirRef(name=child.rsplit("/", 1)[-1])
            for child in children_by_dir.get(dir_path, [])
        ]
        body = folder_to_index(
            concepts=dir_concepts.get(dir_path, []),
            subdirectories=subdirs,
        )
        if not body:
            continue
        if dir_path:
            index_files.append((f"{dir_path}/{INDEX_FILENAME}", body))
        else:
            index_files.append((INDEX_FILENAME, _ROOT_INDEX_FRONTMATTER + body))

    return index_files


def _build_log_files(
    dir_logs: dict[str, list[LogEntry]],
) -> list[tuple[str, str]]:
    """Build ``log.md`` files for every directory that holds concepts.

    Unlike ``index.md``, logs are only synthesized where documents actually live
    (no ancestor synthesis): an empty intermediate directory has nothing to log.
    """
    log_files: list[tuple[str, str]] = []
    for dir_path, entries in dir_logs.items():
        body = folder_to_log(entries)
        if not body:
            continue
        path = f"{dir_path}/{LOG_FILENAME}" if dir_path else LOG_FILENAME
        log_files.append((path, body))
    return log_files


@dataclass
class ExportResult:
    zip_path: str
    export_name: str
    zip_size: int
    skipped_docs: list[str] = field(default_factory=list)


@dataclass
class _SkippedDoc:
    id: int
    title: str
    reason: str


@dataclass
class _ListedDoc:
    id: int
    path: str
    title: str
    source: str
    created_at: str | None


@dataclass
class _WorkspaceWrite:
    documents: list[_ListedDoc]
    skipped: list[_SkippedDoc]
    wrote: bool


async def _write_zip_entries(
    zip_path: str, entries: list[tuple[str, str]], *, fresh: bool
) -> None:
    mode = "w" if fresh else "a"

    def _write() -> None:
        with zipfile.ZipFile(zip_path, mode, zipfile.ZIP_DEFLATED) as zf:
            for path, content in entries:
                zf.writestr(path, content)

    await asyncio.to_thread(_write)


async def _export_workspace_markdown(
    session: AsyncSession,
    workspace_id: int,
    zip_path: str,
    *,
    path_prefix: str = "",
    folder_id: int | None = None,
    fresh: bool = True,
) -> _WorkspaceWrite:
    """Write one workspace's OKF markdown (concepts, index.md, log.md) into zip_path."""
    if folder_id is not None:
        folder = await session.get(Folder, folder_id)
        if not folder or folder.workspace_id != workspace_id:
            raise ValueError("Folder not found")
        target_folder_ids = set(await get_folder_subtree_ids(session, folder_id))
    else:
        target_folder_ids = None

    folder_query = select(Folder).where(Folder.workspace_id == workspace_id)
    if target_folder_ids is not None:
        folder_query = folder_query.where(Folder.id.in_(target_folder_ids))
    folder_result = await session.execute(folder_query)
    folders = list(folder_result.scalars().all())

    folder_path_map = _build_folder_path_map(folders)

    base_doc_query = select(Document).where(Document.workspace_id == workspace_id)
    if target_folder_ids is not None:
        base_doc_query = base_doc_query.where(Document.folder_id.in_(target_folder_ids))
    base_doc_query = base_doc_query.order_by(Document.id)

    used_paths: dict[str, int] = {}
    skipped: list[_SkippedDoc] = []
    listed: list[_ListedDoc] = []
    wrote = False
    is_first_batch = fresh
    dir_concepts: dict[str, list[ConceptRef]] = {}
    dir_logs: dict[str, list[LogEntry]] = {}
    batch_size = 100
    offset = 0

    while True:
        batch_query = base_doc_query.limit(batch_size).offset(offset)
        batch_result = await session.execute(batch_query)
        documents = list(batch_result.scalars().all())
        if not documents:
            break

        entries: list[tuple[str, str]] = []

        for doc in documents:
            if doc.document_type == DocumentType.ARTIFACT:
                continue

            title = doc.title or "Untitled"
            state = _doc_state(doc)
            if state in _SKIP_REASONS and state != "empty":
                skipped.append(_SkippedDoc(id=doc.id, title=title, reason=state))
                continue

            markdown = await resolve_document_markdown(session, doc)
            if not markdown or not markdown.strip():
                skipped.append(_SkippedDoc(id=doc.id, title=title, reason="empty"))
                continue

            if doc.folder_id and doc.folder_id in folder_path_map:
                dir_path = folder_path_map[doc.folder_id]
            else:
                dir_path = ""

            base_name = _sanitize_filename(title)
            if base_name.lower() in _RESERVED_STEMS:
                base_name = f"{base_name}_"
            rel_path = f"{dir_path}/{base_name}.md" if dir_path else f"{base_name}.md"

            if rel_path in used_paths:
                used_paths[rel_path] += 1
                suffix = used_paths[rel_path]
                base_name = f"{base_name}_{suffix}"
                rel_path = (
                    f"{dir_path}/{base_name}.md" if dir_path else f"{base_name}.md"
                )
            used_paths[rel_path] = used_paths.get(rel_path, 0) + 1

            zip_rel = _join_zip_path(path_prefix, rel_path)
            entries.append((zip_rel, document_to_concept(doc, body=markdown)))
            listed.append(
                _ListedDoc(
                    id=doc.id,
                    path=zip_rel,
                    title=title,
                    source=_document_source(doc),
                    created_at=_iso(doc.created_at),
                )
            )

            metadata = (
                doc.document_metadata
                if isinstance(doc.document_metadata, dict)
                else {}
            )
            description = metadata.get("description")
            dir_concepts.setdefault(dir_path, []).append(
                ConceptRef(
                    title=title,
                    filename=f"{base_name}.md",
                    type=okf_type(doc.document_type),
                    description=description
                    if isinstance(description, str) and description.strip()
                    else None,
                )
            )

            changed_at = doc.updated_at or doc.created_at
            dir_logs.setdefault(dir_path, []).append(
                LogEntry(
                    title=title,
                    timestamp=_iso(changed_at),
                )
            )

        if entries:
            await _write_zip_entries(zip_path, entries, fresh=is_first_batch)
            is_first_batch = False
            wrote = True

        offset += batch_size

    index_files = [
        (_join_zip_path(path_prefix, rel), body)
        for rel, body in _build_index_files(dir_concepts)
    ]
    if index_files:
        await _write_zip_entries(zip_path, index_files, fresh=is_first_batch)
        is_first_batch = False
        wrote = True

    log_files = [
        (_join_zip_path(path_prefix, rel), body)
        for rel, body in _build_log_files(dir_logs)
    ]
    if log_files:
        await _write_zip_entries(zip_path, log_files, fresh=is_first_batch)
        wrote = True

    return _WorkspaceWrite(documents=listed, skipped=skipped, wrote=wrote)


async def build_export_zip(
    session: AsyncSession,
    workspace_id: int,
    folder_id: int | None = None,
) -> ExportResult:
    """Build a ZIP archive of markdown documents preserving folder structure.

    Returns an ExportResult with the path to the temp ZIP file.
    The caller is responsible for streaming and cleaning up the file.

    Raises ValueError if folder_id is provided but not found.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    try:
        written = await _export_workspace_markdown(
            session,
            workspace_id,
            tmp_path,
            folder_id=folder_id,
            fresh=True,
        )
        folder_path_map = {}
        if folder_id is not None:
            folder_result = await session.execute(
                select(Folder).where(Folder.workspace_id == workspace_id)
            )
            folder_path_map = _build_folder_path_map(list(folder_result.scalars().all()))

        export_name = "knowledge-base"
        if folder_id is not None and folder_id in folder_path_map:
            export_name = _sanitize_filename(folder_path_map[folder_id].split("/")[0])

        return ExportResult(
            zip_path=tmp_path,
            export_name=export_name,
            zip_size=os.path.getsize(tmp_path),
            skipped_docs=[row.title for row in written.skipped],
        )
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


async def _member_workspaces(session: AsyncSession, user_id: Any) -> list[Workspace]:
    not_deleting = ~Workspace.name.startswith("[DELETING] ")
    result = await session.execute(
        select(Workspace)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        )
        .where(WorkspaceMembership.user_id == user_id, not_deleting)
        .order_by(Workspace.id)
    )
    return list(result.scalars().unique().all())


async def _citation_titles(
    session: AsyncSession, workspace_id: int, payloads: set[str]
) -> dict[str, str]:
    chunk_ids: list[int] = []
    for payload in payloads:
        try:
            chunk_ids.append(int(payload))
        except ValueError:
            continue
    if not chunk_ids:
        return {}
    result = await session.execute(
        select(Chunk.id, Document.title)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(chunk_ids), Document.workspace_id == workspace_id)
    )
    return {str(chunk_id): title for chunk_id, title in result.all()}


def _role_value(role: Any) -> str:
    return role.value if isinstance(role, NewChatMessageRole) else str(role)


async def flatten_workspace_chats(
    session: AsyncSession, workspace_id: int
) -> list[dict[str, Any]]:
    """Flatten new_chat JSONB into contract-3 chats.json threads."""
    result = await session.execute(
        select(NewChatThread)
        .where(
            NewChatThread.workspace_id == workspace_id,
            NewChatThread.source != ARTIFACT_API_SOURCE,
        )
        .options(selectinload(NewChatThread.messages))
        .order_by(NewChatThread.id)
    )
    threads = list(result.scalars().unique().all())

    payloads: set[str] = set()
    for thread in threads:
        for message in thread.messages:
            if _role_value(message.role) not in _CHAT_ROLES:
                continue
            payloads.update(
                raw.strip()
                for raw in _CITATION_RE.findall(extract_text_content(message.content))
            )
    title_by_payload = await _citation_titles(session, workspace_id, payloads)

    exported: list[dict[str, Any]] = []
    for thread in threads:
        messages_out: list[dict[str, Any]] = []
        ordered = sorted(
            thread.messages, key=lambda item: (item.created_at, item.id)
        )
        for message in ordered:
            role = _role_value(message.role)
            if role not in _CHAT_ROLES:
                continue
            text, citations = flatten_message_text(
                extract_text_content(message.content), title_by_payload
            )
            if not text.strip() and not citations:
                continue
            messages_out.append(
                {
                    "role": role,
                    "text": text,
                    "citations": citations,
                    "created_at": _iso(message.created_at),
                }
            )
        if not messages_out:
            continue
        exported.append(
            {
                "id": thread.id,
                "title": thread.title,
                "created_at": _iso(thread.created_at),
                "messages": messages_out,
            }
        )
    return exported


def _manifest_first_zip(staging_path: str, manifest: dict[str, Any]) -> str:
    fd, final_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        with zipfile.ZipFile(final_path, "w", zipfile.ZIP_DEFLATED) as dst:
            dst.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            if os.path.getsize(staging_path) > 0:
                with zipfile.ZipFile(staging_path, "r") as src:
                    for info in src.infolist():
                        dst.writestr(info, src.read(info.filename))
    except Exception:
        if os.path.exists(final_path):
            os.unlink(final_path)
        raise
    finally:
        if os.path.exists(staging_path):
            os.unlink(staging_path)
    return final_path


async def build_account_export_zip(
    session: AsyncSession, user_id: Any
) -> ExportResult:
    """Build a contract-3 ZIP of every workspace the user is a member of."""
    workspaces = await _member_workspaces(session, user_id)
    fd, staging_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    fresh = True
    manifest_workspaces: list[dict[str, Any]] = []
    skipped_titles: list[str] = []

    try:
        for workspace in workspaces:
            prefix = f"workspaces/{workspace.id}/documents"
            written = await _export_workspace_markdown(
                session,
                workspace.id,
                staging_path,
                path_prefix=prefix,
                fresh=fresh,
            )
            if written.wrote:
                fresh = False

            chats = await flatten_workspace_chats(session, workspace.id)
            chats_path = f"workspaces/{workspace.id}/chats.json"
            await _write_zip_entries(
                staging_path,
                [(chats_path, json.dumps(chats, ensure_ascii=False, indent=2))],
                fresh=fresh,
            )
            fresh = False

            skipped_titles.extend(row.title for row in written.skipped)
            manifest_workspaces.append(
                {
                    "id": workspace.id,
                    "name": workspace.name,
                    "created_at": _iso(workspace.created_at),
                    "chats": chats_path,
                    "documents": [
                        {
                            "id": doc.id,
                            "path": doc.path,
                            "title": doc.title,
                            "source": doc.source,
                            "created_at": doc.created_at,
                        }
                        for doc in written.documents
                    ],
                    "skipped": [
                        {"id": row.id, "title": row.title, "reason": row.reason}
                        for row in written.skipped
                    ],
                }
            )

        manifest = {
            "format": _ACCOUNT_FORMAT,
            "exported_at": datetime.now(UTC).isoformat(),
            "workspaces": manifest_workspaces,
        }
        zip_path = _manifest_first_zip(staging_path, manifest)
        staging_path = ""
        return ExportResult(
            zip_path=zip_path,
            export_name="surfsense-export",
            zip_size=os.path.getsize(zip_path),
            skipped_docs=skipped_titles,
        )
    except Exception:
        if staging_path and os.path.exists(staging_path):
            os.unlink(staging_path)
        raise
