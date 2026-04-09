"""Service for exporting knowledge base content as a ZIP archive."""

import logging
import os
import tempfile
import zipfile
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Chunk, Document, Folder
from app.services.folder_service import get_folder_subtree_ids

logger = logging.getLogger(__name__)


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


async def _get_document_markdown(
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
        .order_by(Chunk.id)
    )
    chunks = chunk_result.scalars().all()
    if chunks:
        return "\n\n".join(chunks)

    return None


@dataclass
class ExportResult:
    zip_path: str
    export_name: str
    zip_size: int
    skipped_docs: list[str] = field(default_factory=list)


async def build_export_zip(
    session: AsyncSession,
    search_space_id: int,
    folder_id: int | None = None,
) -> ExportResult:
    """Build a ZIP archive of markdown documents preserving folder structure.

    Returns an ExportResult with the path to the temp ZIP file.
    The caller is responsible for streaming and cleaning up the file.

    Raises ValueError if folder_id is provided but not found.
    """
    if folder_id is not None:
        folder = await session.get(Folder, folder_id)
        if not folder or folder.search_space_id != search_space_id:
            raise ValueError("Folder not found")
        target_folder_ids = set(await get_folder_subtree_ids(session, folder_id))
    else:
        target_folder_ids = None

    folder_query = select(Folder).where(Folder.search_space_id == search_space_id)
    if target_folder_ids is not None:
        folder_query = folder_query.where(Folder.id.in_(target_folder_ids))
    folder_result = await session.execute(folder_query)
    folders = list(folder_result.scalars().all())

    folder_path_map = _build_folder_path_map(folders)

    doc_query = select(Document).where(Document.search_space_id == search_space_id)
    if target_folder_ids is not None:
        doc_query = doc_query.where(Document.folder_id.in_(target_folder_ids))
    doc_result = await session.execute(doc_query)
    documents = list(doc_result.scalars().all())

    fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    try:
        used_paths: dict[str, int] = {}
        skipped_docs: list[str] = []

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc in documents:
                status = doc.status or {}
                state = status.get("state", "ready") if isinstance(status, dict) else "ready"
                if state in ("pending", "processing"):
                    skipped_docs.append(doc.title or "Untitled")
                    continue

                markdown = await _get_document_markdown(session, doc)
                if not markdown or not markdown.strip():
                    continue

                if doc.folder_id and doc.folder_id in folder_path_map:
                    dir_path = folder_path_map[doc.folder_id]
                else:
                    dir_path = ""

                base_name = _sanitize_filename(doc.title or "Untitled")
                file_path = f"{dir_path}/{base_name}.md" if dir_path else f"{base_name}.md"

                if file_path in used_paths:
                    used_paths[file_path] += 1
                    suffix = used_paths[file_path]
                    file_path = (
                        f"{dir_path}/{base_name}_{suffix}.md"
                        if dir_path
                        else f"{base_name}_{suffix}.md"
                    )
                else:
                    used_paths[file_path] = 1

                zf.writestr(file_path, markdown)

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
