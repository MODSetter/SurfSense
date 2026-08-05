"""What a write capability did, so its caller announces without re-reading git."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.knowledge_store.schemas.revision import Change

if TYPE_CHECKING:
    from app.knowledge_store.index.project import Projection


@dataclass(frozen=True)
class Outcome:
    """The result every facade write returns: the revision and what it touched.

    ``revision`` is ``None`` when the workspace is not git-native, the batch was
    empty, or the content was unchanged — the three cases a caller treats alike.
    ``projection`` is populated only when the writer projected rows itself (the
    agent turn); driven consumers read ``changes`` and leave rows to the indexer.
    """

    revision: str | None
    changes: list[Change] = field(default_factory=list)
    projection: Projection | None = None

    def __bool__(self) -> bool:
        return self.revision is not None
