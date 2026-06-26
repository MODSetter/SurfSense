"""Data shapes for resolved ``@``-references.

One type per kind so each carries exactly the fields it needs: documents and
folders have a path, connectors have a provider, chats have neither. ``kind`` is
a class-level discriminator used by the renderer and scope builder.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class ReferenceKind(StrEnum):
    """What the user pointed at; the value is the label shown to the model."""

    DOCUMENT = "document"
    FOLDER = "folder"
    CONNECTOR = "connector"
    CHAT = "chat"


@dataclass(frozen=True)
class _Reference:
    """Identity shared by every reference kind."""

    entity_id: int
    label: str


@dataclass(frozen=True)
class DocumentReference(_Reference):
    """A referenced document, reachable by its virtual path."""

    path: str
    kind: ClassVar[ReferenceKind] = ReferenceKind.DOCUMENT


@dataclass(frozen=True)
class FolderReference(_Reference):
    """A referenced folder, reachable by its virtual path."""

    path: str
    kind: ClassVar[ReferenceKind] = ReferenceKind.FOLDER


@dataclass(frozen=True)
class ConnectorReference(_Reference):
    """A referenced connector account; ``provider`` is its type label."""

    provider: str | None = None
    kind: ClassVar[ReferenceKind] = ReferenceKind.CONNECTOR


@dataclass(frozen=True)
class ChatReference(_Reference):
    """A referenced chat thread; its turns are read on demand, not here."""

    kind: ClassVar[ReferenceKind] = ReferenceKind.CHAT


Reference = DocumentReference | FolderReference | ConnectorReference | ChatReference


__all__ = [
    "ChatReference",
    "ConnectorReference",
    "DocumentReference",
    "FolderReference",
    "Reference",
    "ReferenceKind",
]
