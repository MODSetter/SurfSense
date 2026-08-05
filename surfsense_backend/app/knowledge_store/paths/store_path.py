"""The ``/documents`` namespace as a validated value object.

``StorePath`` is constructed at the boundary so the rest of the module holds a
value it can trust rather than a string it must keep re-checking. Everything
that decides *where* a file lives — naming, resolution, the legacy renderers —
sits above this file and depends on it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

DOCUMENTS_ROOT = "/documents"
"""Root virtual folder for all KB documents."""

PATH_MARKER = "virtual_path"
"""``document_metadata`` key holding the virtual path a row's content lives at.

Written by the store indexer on every converged row, and by the service layer
when a recorded save lands at a new path. Its presence marks a row as
path-addressed (indexer-owned for pruning); its value is the file a delete or
move must act on.
"""


class StorePathError(ValueError):
    """A string could not be read as a path inside the store's namespace."""


@dataclass(frozen=True)
class StorePath:
    """A validated path inside the store's ``/documents`` namespace.

    The two forms differ only by the leading slash: ``virtual_path`` is what the
    agent and the UI see (``/documents/notes/plan.md``); ``store_path`` is what
    git holds (``documents/notes/plan.md``), because the repo keeps the
    ``documents/`` root free for future sibling roots.
    """

    #: Path segments below ``/documents``, e.g. ``["notes", "plan.md"]``.
    segments: tuple[str, ...]

    @classmethod
    def from_virtual(cls, virtual_path: str) -> StorePath:
        """Parse an agent/UI ``/documents/...`` path, rejecting anything else.

        Raises :class:`StorePathError` on a foreign namespace, a traversal
        segment, or an empty segment — a silent mismatch here forks one document
        into two identities on either side of the git<->Postgres boundary.
        """
        if virtual_path != DOCUMENTS_ROOT and not virtual_path.startswith(
            f"{DOCUMENTS_ROOT}/"
        ):
            raise StorePathError(f"Not a {DOCUMENTS_ROOT} path: {virtual_path!r}")
        rel = virtual_path[len(DOCUMENTS_ROOT) :].strip("/")
        return cls(validate_segments(rel.split("/") if rel else ()))

    @classmethod
    def from_store(cls, store_path: str) -> StorePath:
        """Parse a git-repo ``documents/...`` path back into a value."""
        rel = store_path.strip("/")
        parts = [p for p in rel.split("/") if p]
        if not parts or parts[0] != "documents":
            raise StorePathError(f"Not a documents/ path: {store_path!r}")
        return cls(validate_segments(parts[1:]))

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


def validate_segments(segments: Iterable[str]) -> tuple[str, ...]:
    """Reject empty and traversal segments; return the rest as a tuple."""
    out: list[str] = []
    for segment in segments:
        if not segment or segment in (".", ".."):
            raise StorePathError(f"Illegal path segment: {segment!r}")
        out.append(segment)
    return tuple(out)


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
