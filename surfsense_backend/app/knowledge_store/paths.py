"""The store's path vocabulary: on-disk layout and the ``/documents`` namespace.

On-disk layout (:func:`workspace_store_path` and friends) locates a workspace's
git repo and working copies. It stays free of ``app.db`` at module load because
:mod:`app.knowledge_store.store` imports it on the enqueue path.

The ``/documents`` namespace (:class:`StorePath`, :func:`allocate_path`) is the
authored-once model: a path is authored once, recorded on its row, and changes
only by an explicit move. Titles never place files, so a document id never
appears in a path.

The "legacy title->path derivation" section derives a path from a title on
every render and belongs to ``kb_postgres`` until the Phase 5 cut. The store's
write side must not call it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import Document

from app.knowledge_store.settings import load_knowledge_store_settings

DOCUMENTS_ROOT = "/documents"
"""Root virtual folder for all KB documents."""

PATH_MARKER = "virtual_path"
"""``document_metadata`` key holding the virtual path a row's content lives at.

Written by the store indexer on every converged row, and by the service layer
when a recorded save lands at a new path. Its presence marks a row as
path-addressed (indexer-owned for pruning); its value is the file a delete or
move must act on.
"""

_WORKING_COPIES_DIRNAME = ".working_copies"


# --------------------------------------------------------------------------- #
# On-disk layout (light: no ``app.db`` import).
# --------------------------------------------------------------------------- #


def workspace_store_path(workspace_id: int | str) -> Path:
    """Absolute directory holding a single workspace's versioned history."""
    root = load_knowledge_store_settings().root
    return Path(root) / str(workspace_id)


def working_copies_root() -> Path:
    """Absolute directory holding every workspace's working copies."""
    root = load_knowledge_store_settings().root
    return Path(root) / _WORKING_COPIES_DIRNAME


def workspace_working_copies_path(workspace_id: int | str) -> Path:
    """Absolute directory holding a workspace's private working copies."""
    return working_copies_root() / str(workspace_id)


# --------------------------------------------------------------------------- #
# The authored-once ``/documents`` namespace.
# --------------------------------------------------------------------------- #

_INVALID_FILENAME_CHARS = re.compile(r"[\\/:*?\"<>|]+")
_WHITESPACE_RUN = re.compile(r"\s+")
_MAX_SEGMENT_LEN = 180
_COLLISION_SUFFIX = re.compile(r"\s\((\d+)\)$")


class StorePathError(ValueError):
    """A string could not be read as a path inside the store's namespace."""


@dataclass(frozen=True)
class StorePath:
    """A validated path inside the store's ``/documents`` namespace.

    Constructed at the boundary so the rest of the module holds a value it can
    trust rather than a string it must keep re-checking. The two forms differ
    only by the leading slash: ``virtual_path`` is what the agent and the UI
    see (``/documents/notes/plan.md``); ``store_path`` is what git holds
    (``documents/notes/plan.md``), because the repo keeps the ``documents/``
    root free for future sibling roots.
    """

    #: Path segments below ``/documents``, e.g. ``["notes", "plan.md"]``.
    segments: tuple[str, ...]

    @classmethod
    def from_virtual(cls, virtual_path: str) -> StorePath:
        """Parse an agent/UI ``/documents/...`` path, rejecting anything else.

        Raises :class:`StorePathError` on a foreign namespace, a traversal
        segment, or an empty segment — a silent mismatch here forks one
        document into two identities on either side of the git<->Postgres
        boundary.
        """
        if virtual_path != DOCUMENTS_ROOT and not virtual_path.startswith(
            f"{DOCUMENTS_ROOT}/"
        ):
            raise StorePathError(f"Not a {DOCUMENTS_ROOT} path: {virtual_path!r}")
        rel = virtual_path[len(DOCUMENTS_ROOT) :].strip("/")
        return cls(_validate_segments(rel.split("/") if rel else ()))

    @classmethod
    def from_store(cls, store_path: str) -> StorePath:
        """Parse a git-repo ``documents/...`` path back into a value."""
        rel = store_path.strip("/")
        parts = [p for p in rel.split("/") if p]
        if not parts or parts[0] != "documents":
            raise StorePathError(f"Not a documents/ path: {store_path!r}")
        return cls(_validate_segments(parts[1:]))

    @property
    def virtual_path(self) -> str:
        """Agent/UI form: ``/documents/...``."""
        return DOCUMENTS_ROOT + "".join(f"/{s}" for s in self.segments)

    @property
    def store_path(self) -> str:
        """Git-repo form: ``documents/...`` (no leading slash)."""
        return "documents" + "".join(f"/{s}" for s in self.segments)

    @property
    def folder_parts(self) -> tuple[str, ...]:
        """Folder segments above the file (empty when at the root)."""
        return self.segments[:-1]

    @property
    def name(self) -> str:
        """Basename, or ``""`` for the root itself."""
        return self.segments[-1] if self.segments else ""


def _validate_segments(segments: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    for segment in segments:
        if not segment or segment in (".", ".."):
            raise StorePathError(f"Illegal path segment: {segment!r}")
        out.append(segment)
    return tuple(out)


def safe_folder_segment(value: str, *, fallback: str = "folder") -> str:
    """Sanitize one folder name into a path-safe segment."""
    name = _INVALID_FILENAME_CHARS.sub("_", value).strip()
    name = _WHITESPACE_RUN.sub(" ", name)
    if not name:
        return fallback
    if len(name) > _MAX_SEGMENT_LEN:
        name = name[:_MAX_SEGMENT_LEN].rstrip()
    return name


def normalize_filename(value: str, *, fallback: str = "untitled.md") -> str:
    """Sanitize text into a filesystem-safe filename, defaulting to ``.md``.

    A name the author already gave an extension keeps it; a name without one
    gets ``.md`` because git holds markdown.
    """
    name = _INVALID_FILENAME_CHARS.sub("_", value).strip()
    name = _WHITESPACE_RUN.sub(" ", name)
    if not name:
        name = fallback
    if len(name) > _MAX_SEGMENT_LEN:
        name = name[:_MAX_SEGMENT_LEN].rstrip()
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem or not ext or len(ext) > 12 or " " in ext:
        # No real extension (a lone trailing dot, or a "." inside prose): the
        # file is markdown, so say so rather than guess a type from the title.
        name = f"{name}.md"
    return name


def markdown_name_for_source(source_filename: str) -> str:
    """Filename an uploaded ``report.pdf`` gets in the tree: ``report.md``.

    Git holds the extracted markdown, not the source bytes, so the tree name
    matches the content. The original filename stays in ``document_files`` for
    the download path.
    """
    sanitized = normalize_filename(source_filename)
    stem = sanitized.rsplit(".", 1)[0]
    return f"{stem}.md" if stem else "untitled.md"


def allocate_path(
    *,
    name: str,
    folder_parts: Iterable[str],
    taken: set[str],
) -> StorePath:
    """Author a fresh path, resolving collisions once and deterministically.

    ``taken`` is the set of virtual paths already occupied (in the tree, or
    reserved earlier in the same batch). A collision appends ``" (2)"``,
    ``" (3)"``, ... before the extension — never a document id, which would tie
    the path to a row and reintroduce the churn the authored-once model removes.
    The chosen path is added to ``taken`` so the next call in the batch sees it.
    """
    folders = tuple(safe_folder_segment(p) for p in folder_parts if str(p).strip())
    filename = normalize_filename(name)
    candidate = StorePath(_validate_segments((*folders, filename)))
    if candidate.virtual_path not in taken:
        taken.add(candidate.virtual_path)
        return candidate

    stem, dot, ext = filename.rpartition(".")
    base, extension = (stem, f".{ext}") if dot else (filename, "")
    counter = 2
    while True:
        disambiguated = f"{base} ({counter}){extension}"
        candidate = StorePath(_validate_segments((*folders, disambiguated)))
        if candidate.virtual_path not in taken:
            taken.add(candidate.virtual_path)
            return candidate
        counter += 1


def parse_documents_path(virtual_path: str) -> tuple[list[str], str]:
    """Parse a ``/documents/...`` path into ``(folder_parts, document_title)``.

    The title keeps whatever extension the author gave the file; only the
    authored-once model runs, so there is no ``(doc_id)`` suffix to strip.
    """
    try:
        path = StorePath.from_virtual(virtual_path)
    except StorePathError:
        return [], ""
    return list(path.folder_parts), path.name


# --------------------------------------------------------------------------- #
# Reverse resolution: a stored path back to its row.
# --------------------------------------------------------------------------- #


async def virtual_path_to_doc(
    session: AsyncSession,
    *,
    workspace_id: int,
    virtual_path: str,
) -> Document | None:
    """Resolve a virtual path to the ``Document`` that lives at it.

    The authored-once model stores the path on the row (``PATH_MARKER``), so the
    marker lookup is the answer for anything git-native. The legacy fallbacks
    below cover rows a not-yet-flipped workspace never stamped a marker onto.
    """
    from sqlalchemy import select

    from app.db import Document, DocumentType
    from app.utils.document_converters import generate_unique_identifier_hash

    try:
        path = StorePath.from_virtual(virtual_path)
    except StorePathError:
        return None
    if not path.segments:
        return None

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


# --------------------------------------------------------------------------- #
# Legacy title->path derivation. Read-side renderers only, until the Phase 5 cut.
# --------------------------------------------------------------------------- #


def to_store_path(virtual_path: str) -> str:
    """Legacy shim: agent-facing ``/documents/...`` -> git-repo ``documents/...``."""
    return StorePath.from_virtual(virtual_path).store_path


def to_virtual_path(store_path: str) -> str:
    """Legacy shim: git-repo ``documents/...`` -> agent-facing ``/documents/...``."""
    return StorePath.from_store(store_path).virtual_path


def safe_filename(value: str, *, fallback: str = "untitled.xml") -> str:
    """Legacy: force arbitrary text into an ``.xml`` filename (renderers only)."""
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
    """Legacy: strip a trailing ``" (<doc_id>).xml"`` suffix; ``(stem, doc_id)``."""
    match = _SUFFIX_PATTERN.search(filename)
    if match:
        doc_id = int(match.group(1))
        return filename[: match.start()], doc_id
    if filename.lower().endswith(".xml"):
        return filename[:-4], None
    return filename, None


@dataclass
class PathIndex:
    """Legacy in-memory occupancy snapshot used by :func:`doc_to_virtual_path`."""

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
    """Legacy: build a :class:`PathIndex` for a workspace's render."""
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
    """Legacy: derive the canonical virtual path for a document from its title."""
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
    metadata: Mapping[str, Any] | None,
    doc_id: int | None,
    title: str,
    folder_id: int | None,
    index: PathIndex,
) -> str:
    """Legacy: where a row's content lives, per its :data:`PATH_MARKER`.

    Rows with a marker return it verbatim; rows without fall back to derivation.
    """
    recorded = (metadata or {}).get(PATH_MARKER)
    if isinstance(recorded, str) and recorded.startswith(f"{DOCUMENTS_ROOT}/"):
        if doc_id is not None:
            index.occupants[recorded] = doc_id
        return recorded
    return doc_to_virtual_path(
        doc_id=doc_id, title=title, folder_id=folder_id, index=index
    )


__all__ = [
    "DOCUMENTS_ROOT",
    "PATH_MARKER",
    "PathIndex",
    "StorePath",
    "StorePathError",
    "allocate_path",
    "build_path_index",
    "doc_to_virtual_path",
    "markdown_name_for_source",
    "normalize_filename",
    "parse_doc_id_suffix",
    "parse_documents_path",
    "safe_filename",
    "safe_folder_segment",
    "to_store_path",
    "to_virtual_path",
    "virtual_path_of",
    "virtual_path_to_doc",
    "workspace_store_path",
    "workspace_working_copies_path",
    "working_copies_root",
]
