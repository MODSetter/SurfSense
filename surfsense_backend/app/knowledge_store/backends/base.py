"""Storage-engine contract behind the facade; the seam for swapping engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ChangeKind = Literal["added", "modified", "removed"]


@dataclass(frozen=True)
class Revision:
    """One recorded point in a workspace's history (a whole-tree snapshot)."""

    id: str
    author: str
    message: str
    created_at: datetime


@dataclass(frozen=True)
class Change:
    """One path's change within a revision."""

    path: str
    kind: ChangeKind
    #: Content address after the change (``None`` when removed).
    content_id: str | None


@dataclass(frozen=True)
class TrackedPath:
    """One path stored at a revision, with its content address."""

    path: str
    content_id: str


class VersionedContentStore(ABC):
    """Append-only, content-addressed history for a single workspace."""

    @abstractmethod
    def ensure_exists(self) -> None:
        """Create the store if absent; a no-op once it exists."""

    @abstractmethod
    def record(
        self,
        *,
        writes: Mapping[str, bytes],
        removes: Iterable[str],
        message: str,
        author: str,
    ) -> str | None:
        """Append ``writes`` and ``removes`` to history as one revision.

        Returns the revision id, or ``None`` when nothing changed.
        """

    @abstractmethod
    def read(self, path: str) -> bytes | None:
        """Current bytes of ``path``, or ``None`` if it does not exist."""

    @abstractmethod
    def read_as_of(self, revision: str, path: str) -> bytes:
        """Bytes of ``path`` as of ``revision``. Raises if absent there."""

    @abstractmethod
    def list_revisions(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[Revision]:
        """Revisions newest-first, optionally scoped to a single path."""

    @abstractmethod
    def list_changes(self, revision: str) -> list[Change]:
        """Paths added, modified, or removed by ``revision`` (vs its parent)."""

    @abstractmethod
    def list_paths(self, revision: str) -> list[TrackedPath]:
        """Every path stored at ``revision``, with its content address."""

    @abstractmethod
    def get_current_revision(self) -> str | None:
        """Id of the current whole-store snapshot, or ``None`` when empty."""

    @staticmethod
    @abstractmethod
    def compute_content_id(data: bytes) -> str:
        """Stable content address for ``data``, independent of any path."""
