"""The remote catalog's row, and what its pure functions take in."""

from dataclasses import dataclass
from enum import StrEnum

from modules.llm.catalog.remote.support import Supports
from modules.llm.catalog.source import Source
from modules.llm.model_type import ModelType

__all__ = [
    "CUSTOM",
    "Availability", "ConnectionInfo", "ConnectionRef", "ListedModel", "RemoteRow"]


# The catalog provider of a connection whose endpoint the manifest does not list.
CUSTOM = "custom"


class Availability(StrEnum):
    """Whether the user can use this model through this connection, right now."""

    NOT_CONNECTED = "not_connected"
    UNCHECKED = "unchecked"
    AVAILABLE = "available"
    # Retired, or the key cannot reach it.
    NOT_SERVED = "not_served"
    COULD_NOT_CHECK = "could_not_check"
    # The provider or the model cannot be called; `reason` says why.
    UNUSABLE = "unusable"


@dataclass(frozen=True)
class ConnectionInfo:
    """A saved connection, as the catalog needs it."""

    id: int
    label: str
    catalog_provider: str


@dataclass(frozen=True)
class ConnectionRef:
    id: int
    label: str


@dataclass(frozen=True)
class ListedModel:
    """One id a connection's live listing returned, already classified."""

    name: str
    types: tuple[ModelType, ...]
    known: bool


@dataclass(frozen=True)
class RemoteRow:
    provider: str
    connection: ConnectionRef | None
    model_id: str
    name: str
    types: frozenset[ModelType]
    known: bool
    # Decided once, by the rule selection uses, and empty when unusable.
    selectable_for: tuple[ModelType, ...]
    supports: Supports | None
    status: str | None
    availability: Availability
    reason: str | None = None
    source: Source = Source.REMOTE
