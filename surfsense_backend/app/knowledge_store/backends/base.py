"""Storage-engine contract behind the facade; the seam for swapping engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredRevision:
    """One recorded point in a workspace's history."""

    id: str
    author: str
    message: str
    created_at: datetime


class VersionedContentStore(ABC):
    """Append-only, content-addressed history for a single workspace."""

    @abstractmethod
    def ensure(self) -> None:
        """Create the store if absent; a no-op once it exists."""

    @abstractmethod
    def commit(
        self,
        *,
        writes: Mapping[str, bytes],
        removes: Iterable[str],
        message: str,
        author: str,
    ) -> str | None:
        """Snapshot ``writes`` and ``removes`` as one revision.

        Returns the revision id, or ``None`` when nothing changed.
        """

    @abstractmethod
    def read(self, path: str) -> bytes | None:
        """Current bytes of ``path``, or ``None`` if it does not exist."""

    @abstractmethod
    def read_at(self, revision: str, path: str) -> bytes:
        """Return a path's bytes as of ``revision``. Raises if absent there."""

    @abstractmethod
    def history(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[StoredRevision]:
        """Revisions newest-first, optionally scoped to a single path."""

    @abstractmethod
    def current_revision(self) -> str | None:
        """The current revision id, or ``None`` for an empty store."""

    @staticmethod
    @abstractmethod
    def content_id(data: bytes) -> str:
        """Stable content address for ``data``, independent of any path."""
