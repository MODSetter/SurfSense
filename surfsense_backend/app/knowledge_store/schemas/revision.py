"""History value objects: a recorded revision, one path's change, a tracked path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ChangeKind = Literal["added", "modified", "removed", "renamed"]


@dataclass(frozen=True)
class Revision:
    """One recorded point in a workspace's history (a whole-tree snapshot)."""

    id: str
    #: Whose content change this is (the acting user).
    author: str
    #: Who recorded it (the agent for agent turns; equals author otherwise).
    committer: str
    message: str
    created_at: datetime


@dataclass(frozen=True)
class Change:
    """One path's change within a revision."""

    path: str
    kind: ChangeKind
    #: Content address after the change (``None`` when removed).
    content_id: str | None
    #: Where a renamed path came from (``None`` for every other kind).
    previous_path: str | None = None


@dataclass(frozen=True)
class TrackedPath:
    """One path stored at a revision, with its content address."""

    path: str
    content_id: str
