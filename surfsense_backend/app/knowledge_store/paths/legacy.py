"""Legacy title->path derivation for ``kb_postgres``. Deleted at the Phase 5 cut."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.knowledge_store.paths.naming import (
    _INVALID_FILENAME_CHARS,
    _MAX_SEGMENT_LEN,
    _WHITESPACE_RUN,
    safe_folder_segment,
)
from app.knowledge_store.paths.store_path import (
    DOCUMENTS_ROOT,
    StorePath,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def to_store_path(virtual_path: str) -> str:
    """``/documents/...`` -> ``documents/...``."""
    return StorePath.from_virtual(virtual_path).store_path


def to_virtual_path(store_path: str) -> str:
    """``documents/...`` -> ``/documents/...``."""
    return StorePath.from_store(store_path).virtual_path


def safe_filename(value: str, *, fallback: str = "untitled.xml") -> str:
    """Force text into an ``.xml`` filename."""
    name = _INVALID_FILENAME_CHARS.sub("_", value).strip()
    name = _WHITESPACE_RUN.sub(" ", name)
    if not name:
        name = fallback
    if len(name) > _MAX_SEGMENT_LEN:
        name = name[:_MAX_SEGMENT_LEN].rstrip()
    if not name.lower().endswith(".xml"):
        name = f"{name}.xml"
    return name


def _suffix_with_doc_id(filename: str, doc_id: int | None) -> str:
    if doc_id is None:
        return filename
    if not filename.lower().endswith(".xml"):
        return f"{filename} ({doc_id}).xml"
    stem = filename[:-4]
    return f"{stem} ({doc_id}).xml"


_SUFFIX_PATTERN = re.compile(r"\s\((\d+)\)\.xml$", re.IGNORECASE)


def parse_doc_id_suffix(filename: str) -> tuple[str, int | None]:
    """Strip a trailing ``" (<doc_id>).xml"``; return ``(stem, doc_id)``."""
    match = _SUFFIX_PATTERN.search(filename)
    if match:
        doc_id = int(match.group(1))
        return filename[: match.start()], doc_id
    if filename.lower().endswith(".xml"):
        return filename[:-4], None
    return filename, None


@dataclass
class PathIndex:
    """A workspace's folder paths and current path occupants."""

    folder_paths: dict[int, str] = field(default_factory=dict)
    occupants: dict[str, int] = field(default_factory=dict)


async def _build_folder_paths(
    session: AsyncSession,
    workspace_id: int,
) -> dict[int, str]:
    from sqlalchemy import select

    from app.db import Folder

    result = await session.execute(
        select(Folder.id, Folder.name, Folder.parent_id).where(
            Folder.workspace_id == workspace_id
        )
    )
    rows = result.all()
    by_id = {row.id: {"name": row.name, "parent_id": row.parent_id} for row in rows}
    cache: dict[int, str] = {}

    def resolve(folder_id: int) -> str:
        if folder_id in cache:
            return cache[folder_id]
        parts: list[str] = []
        cursor: int | None = folder_id
        visited: set[int] = set()
        while cursor is not None and cursor in by_id and cursor not in visited:
            visited.add(cursor)
            entry = by_id[cursor]
            parts.append(safe_folder_segment(str(entry["name"])))
            cursor = entry["parent_id"]
        parts.reverse()
        path = f"{DOCUMENTS_ROOT}/" + "/".join(parts) if parts else DOCUMENTS_ROOT
        cache[folder_id] = path
        return path

    for folder_id in by_id:
        resolve(folder_id)
    return cache


async def build_path_index(
    session: AsyncSession,
    workspace_id: int,
    *,
    populate_occupants: bool = True,
) -> PathIndex:
    """Build a :class:`PathIndex` for a workspace."""
    from sqlalchemy import select

    from app.db import Document

    folder_paths = await _build_folder_paths(session, workspace_id)
    occupants: dict[str, int] = {}
    if populate_occupants:
        rows = await session.execute(
            select(Document.id, Document.title, Document.folder_id).where(
                Document.workspace_id == workspace_id,
            )
        )
        for row in rows.all():
            base = folder_paths.get(row.folder_id, DOCUMENTS_ROOT)
            filename = safe_filename(str(row.title or "untitled"))
            path = f"{base}/{filename}"
            if path in occupants and occupants[path] != row.id:
                path = f"{base}/{_suffix_with_doc_id(filename, row.id)}"
            occupants[path] = row.id
    return PathIndex(folder_paths=folder_paths, occupants=occupants)


def doc_to_virtual_path(
    *,
    doc_id: int | None,
    title: str,
    folder_id: int | None,
    index: PathIndex,
) -> str:
    """Derive a document's virtual path from its title, breaking collisions by id."""
    base = index.folder_paths.get(folder_id, DOCUMENTS_ROOT)
    filename = safe_filename(str(title or "untitled"))
    path = f"{base}/{filename}"
    occupant = index.occupants.get(path)
    if occupant is not None and occupant != doc_id:
        path = f"{base}/{_suffix_with_doc_id(filename, doc_id)}"
    if doc_id is not None:
        index.occupants[path] = doc_id
    return path


def virtual_path_of(
    *,
    path: str | None,
    doc_id: int | None,
    title: str,
    folder_id: int | None,
    index: PathIndex,
) -> str:
    """A row's path from its ``path`` column, else derived from its title."""
    if isinstance(path, str) and path.startswith(f"{DOCUMENTS_ROOT}/"):
        if doc_id is not None:
            index.occupants[path] = doc_id
        return path
    return doc_to_virtual_path(
        doc_id=doc_id, title=title, folder_id=folder_id, index=index
    )


def parse_documents_path(virtual_path: str) -> tuple[list[str], str]:
    """Split a ``/documents/...`` path into ``(folder_parts, title)``.

    The title is the basename with its ``.xml`` extension and any trailing
    ``" (<doc_id>)"`` disambiguation suffix stripped — the inverse of the
    derivation above, so a path the indexer reads names the same document the
    writer meant. ``([], "")`` for a foreign path.
    """
    if not virtual_path or not virtual_path.startswith(DOCUMENTS_ROOT):
        return [], ""
    rel = virtual_path[len(DOCUMENTS_ROOT) :].strip("/")
    parts = [p for p in rel.split("/") if p]
    if not parts:
        return [], ""
    stem, _ = parse_doc_id_suffix(parts[-1])
    if stem.endswith(".xml"):
        stem = stem[:-4]
    return parts[:-1], stem
