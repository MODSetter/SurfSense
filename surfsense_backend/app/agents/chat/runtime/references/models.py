"""Data shapes for a resolved ``@``-reference."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReferenceKind(str, Enum):
    """What the user pointed at; the value is the label shown to the model."""

    DOCUMENT = "document"
    FOLDER = "folder"
    CONNECTOR = "connector"
    CHAT = "chat"


@dataclass(frozen=True)
class ResolvedReference:
    """A resolved reference: identity plus the bits a pointer line needs."""

    kind: ReferenceKind
    entity_id: int
    label: str
    path: str | None = None  # document/folder virtual path
    provider: str | None = None  # connector provider, e.g. "Gmail"


__all__ = ["ReferenceKind", "ResolvedReference"]
