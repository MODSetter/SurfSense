"""The ``/documents`` namespace as a validated value object."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

DOCUMENTS_ROOT = "/documents"

#: ``document_metadata`` key holding the virtual path a row's content lives at.
PATH_MARKER = "virtual_path"

#: Marks an explicitly-created folder so an empty one survives in git, which
#: cannot store a bare directory. Engine-internal: never a document.
KEEP_FILE = ".keep"


class StorePathError(ValueError):
    """A string is not a path inside the store's namespace."""


@dataclass(frozen=True)
class StorePath:
    """A validated path inside ``/documents``.

    ``virtual_path`` is the agent/UI form (``/documents/notes/plan.md``);
    ``store_path`` is the git form (``documents/notes/plan.md``).
    """

    segments: tuple[str, ...]

    @classmethod
    def from_virtual(cls, virtual_path: str) -> StorePath:
        """Parse a ``/documents/...`` path; reject a foreign or unsafe one."""
        if virtual_path != DOCUMENTS_ROOT and not virtual_path.startswith(
            f"{DOCUMENTS_ROOT}/"
        ):
            raise StorePathError(f"Not a {DOCUMENTS_ROOT} path: {virtual_path!r}")
        rel = virtual_path[len(DOCUMENTS_ROOT) :].strip("/")
        segments = validate_segments(rel.split("/") if rel else ())
        if segments and segments[-1] == KEEP_FILE:
            raise StorePathError(f"{KEEP_FILE} is a folder marker, not a document")
        return cls(segments)

    @classmethod
    def from_store(cls, store_path: str) -> StorePath:
        """Parse a ``documents/...`` git path."""
        rel = store_path.strip("/")
        parts = [p for p in rel.split("/") if p]
        if not parts or parts[0] != "documents":
            raise StorePathError(f"Not a documents/ path: {store_path!r}")
        return cls(validate_segments(parts[1:]))

    @property
    def virtual_path(self) -> str:
        return DOCUMENTS_ROOT + "".join(f"/{s}" for s in self.segments)

    @property
    def store_path(self) -> str:
        return "documents" + "".join(f"/{s}" for s in self.segments)

    @property
    def folder_parts(self) -> tuple[str, ...]:
        return self.segments[:-1]

    @property
    def name(self) -> str:
        return self.segments[-1] if self.segments else ""


def recorded_virtual_path(
    document_metadata: Mapping[str, object] | None, path: str | None
) -> str | None:
    """The path a doc already lives at: the durable column, then the marker.

    Both are ``/documents/...`` virtual paths. The column is what writers set and
    is authoritative; the marker is legacy and, once writers stop stamping it, can
    go stale — so it is only the fallback for a row written before 189 filled the
    column. The live recorder and the Phase-5 seeder share this one reader, so a
    re-sync and a re-seed can never pin one row to two different files.
    """
    prefix = f"{DOCUMENTS_ROOT}/"
    for value in (path, (document_metadata or {}).get(PATH_MARKER)):
        if isinstance(value, str) and value.startswith(prefix):
            return value
    return None


def validate_segments(segments: Iterable[str]) -> tuple[str, ...]:
    """Reject empty and traversal segments."""
    out: list[str] = []
    for segment in segments:
        if not segment or segment in (".", ".."):
            raise StorePathError(f"Illegal path segment: {segment!r}")
        out.append(segment)
    return tuple(out)
