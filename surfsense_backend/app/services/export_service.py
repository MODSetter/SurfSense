"""Service for exporting knowledge base content as a ZIP archive."""

import asyncio
import logging
import os
import tempfile
import zipfile
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Chunk, Document, Folder
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

logger = logging.getLogger(__name__)

# Root index.md declares the targeted OKF version in frontmatter - the one place
# the spec permits frontmatter in an index file.
_ROOT_INDEX_FRONTMATTER = '---\nokf_version: "0.1"\n---\n\n'

_RESERVED_STEMS = {"index", "log"}


def _sanitize_filename(title: str) -> str:
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in title).strip()
    return safe[:80] or "document"


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

    batch_size = 100

    base_doc_query = select(Document).where(Document.workspace_id == workspace_id)
    if target_folder_ids is not None:
        base_doc_query = base_doc_query.where(Document.folder_id.in_(target_folder_ids))
    base_doc_query = base_doc_query.order_by(Document.id)

    fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    used_paths: dict[str, int] = {}
    skipped_docs: list[str] = []
    is_first_batch = True
    # dir path -> concepts it holds, accumulated across batches for index.md.
    dir_concepts: dict[str, list[ConceptRef]] = {}
    # dir path -> log entries it holds, accumulated across batches for log.md.
    dir_logs: dict[str, list[LogEntry]] = {}

    try:
        offset = 0
        while True:
            batch_query = base_doc_query.limit(batch_size).offset(offset)
            batch_result = await session.execute(batch_query)
            documents = list(batch_result.scalars().all())
            if not documents:
                break

            entries: list[tuple[str, str]] = []

            for doc in documents:
                status = doc.status or {}
                state = (
                    status.get("state", "ready")
                    if isinstance(status, dict)
                    else "ready"
                )
                if state in ("pending", "processing"):
                    skipped_docs.append(doc.title or "Untitled")
                    continue

                markdown = await resolve_document_markdown(session, doc)
                if not markdown or not markdown.strip():
                    continue

                if doc.folder_id and doc.folder_id in folder_path_map:
                    dir_path = folder_path_map[doc.folder_id]
                else:
                    dir_path = ""

                base_name = _sanitize_filename(doc.title or "Untitled")
                # Never collide with reserved OKF filenames (index.md, log.md).
                if base_name.lower() in _RESERVED_STEMS:
                    base_name = f"{base_name}_"
                file_path = (
                    f"{dir_path}/{base_name}.md" if dir_path else f"{base_name}.md"
                )

                if file_path in used_paths:
                    used_paths[file_path] += 1
                    suffix = used_paths[file_path]
                    base_name = f"{base_name}_{suffix}"
                    file_path = (
                        f"{dir_path}/{base_name}.md"
                        if dir_path
                        else f"{base_name}.md"
                    )
                used_paths[file_path] = used_paths.get(file_path, 0) + 1

                concept = document_to_concept(doc, body=markdown)
                entries.append((file_path, concept))

                metadata = (
                    doc.document_metadata
                    if isinstance(doc.document_metadata, dict)
                    else {}
                )
                description = metadata.get("description")
                dir_concepts.setdefault(dir_path, []).append(
                    ConceptRef(
                        title=doc.title or "Untitled",
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
                        title=doc.title or "Untitled",
                        timestamp=changed_at.isoformat() if changed_at else None,
                    )
                )

            if entries:
                mode = "w" if is_first_batch else "a"
                batch_entries = entries

                def _write_batch(m: str = mode, e: list = batch_entries) -> None:
                    with zipfile.ZipFile(tmp_path, m, zipfile.ZIP_DEFLATED) as zf:
                        for path, content in e:
                            zf.writestr(path, content)

                await asyncio.to_thread(_write_batch)
                is_first_batch = False

            offset += batch_size

        index_files = _build_index_files(dir_concepts)
        if index_files:
            mode = "w" if is_first_batch else "a"

            def _write_indexes(m: str = mode, e: list = index_files) -> None:
                with zipfile.ZipFile(tmp_path, m, zipfile.ZIP_DEFLATED) as zf:
                    for path, content in e:
                        zf.writestr(path, content)

            await asyncio.to_thread(_write_indexes)
            is_first_batch = False

        log_files = _build_log_files(dir_logs)
        if log_files:
            mode = "w" if is_first_batch else "a"

            def _write_logs(m: str = mode, e: list = log_files) -> None:
                with zipfile.ZipFile(tmp_path, m, zipfile.ZIP_DEFLATED) as zf:
                    for path, content in e:
                        zf.writestr(path, content)

            await asyncio.to_thread(_write_logs)
            is_first_batch = False

        export_name = "knowledge-base"
        if folder_id is not None and folder_id in folder_path_map:
            export_name = _sanitize_filename(folder_path_map[folder_id].split("/")[0])

        return ExportResult(
            zip_path=tmp_path,
            export_name=export_name,
            zip_size=os.path.getsize(tmp_path),
            skipped_docs=skipped_docs,
        )

    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
