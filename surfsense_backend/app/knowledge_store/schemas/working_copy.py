"""A private on-disk copy of the store's content, open for one unit of work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkingCopy:
    """A checkout of the store's content, opened for one turn's file ops."""

    id: str
    path: Path
    #: Revision the copy was opened at (``None`` when the store was empty).
    base_revision: str | None
