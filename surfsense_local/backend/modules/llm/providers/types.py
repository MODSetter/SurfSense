from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    """A model a provider can answer with, once it is installed."""

    name: str
    installed: bool
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogEntry:
    """A model a provider offers to download, and its size."""

    name: str
    label: str
    size_gb: float
    installed: bool = False


@dataclass(frozen=True)
class Message:
    """One turn of a conversation handed to a generator."""

    role: str
    content: str


@dataclass(frozen=True)
class DownloadProgress:
    """How far a model download has come, as the runtime reports it."""

    status: str
    completed: int = 0
    total: int = 0
