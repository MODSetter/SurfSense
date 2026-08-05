"""Reverse resolution: a stored path back to the ``Document`` that lives at it.

The authored-once model stores the path on the row (``PATH_MARKER``), so the
marker lookup is the answer for anything git-native. The fallbacks below cover
rows a not-yet-flipped workspace never stamped a marker onto.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.knowledge_store.paths.legacy import parse_doc_id_suffix, safe_filename
from app.knowledge_store.paths.naming import normalize_filename, safe_folder_segment
from app.knowledge_store.paths.store_path import (
    PATH_MARKER,
    StorePath,
    StorePathError,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import Document


async def virtual_path_to_doc(
    session: AsyncSession,
    *,
    workspace_id: int,
    virtual_path: str,
) -> Document | None:
    """Resolve a virtual path to the ``Document`` that lives at it."""
    from sqlalchemy import select

    from app.db import Document, DocumentType
    from app.utils.document_converters import generate_unique_identifier_hash

    try:
        path = StorePath.from_virtual(virtual_path)
    except StorePathError:
        return None
    if not path.segments:
        return None

    # The healed column first: an index hit on the authored-once identity.
    by_column = await session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.path == virtual_path,
        )
    )
    document = by_column.scalars().first()
    if document is not None:
        return document

    # The marker it is healed from, for rows written before the column existed.
    marked = await session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.document_metadata[PATH_MARKER].as_string() == virtual_path,
        )
    )
    document = marked.scalars().first()
    if document is not None:
        return document

    unique_hash = generate_unique_identifier_hash(
        DocumentType.NOTE, virtual_path, workspace_id
    )
    result = await session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.unique_identifier_hash == unique_hash,
        )
    )
    document = result.scalar_one_or_none()
    if document is not None:
        return document

    # Legacy fallback: a path rendered with a ``" (<doc_id>).xml"`` suffix by
    # ``doc_to_virtual_path`` carries its own row id. Harmless for git-native
    # paths, which never carry the suffix.
    _stem, suffix_doc_id = parse_doc_id_suffix(path.name)
    if suffix_doc_id is not None:
        by_id = await session.execute(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.id == suffix_doc_id,
            )
        )
        document = by_id.scalar_one_or_none()
        if document is not None:
            return document

    return await _resolve_by_title(session, workspace_id, path)


async def _resolve_by_title(
    session: AsyncSession, workspace_id: int, path: StorePath
) -> Document | None:
    """Last resort for unmarked rows: match a title in the resolved folder.

    Connector-imported titles carry characters ``normalize_filename`` replaces,
    so the tree name is lossy; the folder scan re-encodes each candidate title
    to recover the row the agent passed a filename back for.
    """
    from sqlalchemy import select

    from app.db import Document

    folder_id = await _resolve_folder_id(
        session, workspace_id=workspace_id, folder_parts=list(path.folder_parts)
    )
    basename = path.name
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename

    for candidate in dict.fromkeys([basename, stem]):
        if not candidate:
            continue
        query = select(Document).where(
            Document.workspace_id == workspace_id,
            Document.title == candidate,
        )
        query = (
            query.where(Document.folder_id.is_(None))
            if folder_id is None
            else query.where(Document.folder_id == folder_id)
        )
        result = await session.execute(query)
        document = result.scalars().first()
        if document is not None:
            return document

    folder_scan = select(Document).where(Document.workspace_id == workspace_id)
    folder_scan = (
        folder_scan.where(Document.folder_id.is_(None))
        if folder_id is None
        else folder_scan.where(Document.folder_id == folder_id)
    )
    result = await session.execute(folder_scan)
    for candidate_doc in result.scalars().all():
        title = str(candidate_doc.title or "untitled")
        # Match either encoding: the authored-once name a git-native row carries,
        # or the legacy ``.xml`` name a not-yet-flipped renderer produced.
        if basename in (normalize_filename(title), safe_filename(title)):
            return candidate_doc
    return None


async def _resolve_folder_id(
    session: AsyncSession,
    *,
    workspace_id: int,
    folder_parts: list[str],
) -> int | None:
    """Leaf folder id for a chain of folder names; ``None`` if any is missing."""
    from sqlalchemy import select

    from app.db import Folder

    if not folder_parts:
        return None
    parent_id: int | None = None
    for raw in folder_parts:
        name = safe_folder_segment(raw)
        query = select(Folder.id).where(
            Folder.workspace_id == workspace_id,
            Folder.name == name,
        )
        query = (
            query.where(Folder.parent_id.is_(None))
            if parent_id is None
            else query.where(Folder.parent_id == parent_id)
        )
        row = (await session.execute(query)).first()
        if row is None:
            return None
        parent_id = row[0]
    return parent_id
