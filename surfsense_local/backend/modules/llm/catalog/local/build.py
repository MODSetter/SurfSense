"""A build: the files, each with a role, that run as one model. Every engine's builds share it."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FileRole(StrEnum):
    WEIGHTS = "weights"
    PROJECTOR = "projector"


@dataclass(frozen=True)
class BuildFile:
    """One file of a build, pinned where the listing allowed it.

    `gguf` holds header keys under llama.cpp's own names: committed for a curated
    projector, read live for a searched one, so both answer through one rule.
    """

    role: FileRole
    path: str
    size_bytes: int
    sha256: str | None = None
    repo: str = ""
    revision: str = "main"
    gguf: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Build:
    """A set of files that runs as one model. Split weights list every part."""

    quantization: str
    files: tuple[BuildFile, ...]

    @property
    def weights(self) -> BuildFile:
        """The first weights file, which is the one the runtime is pointed at."""
        return next(f for f in self.files if f.role is FileRole.WEIGHTS)

    @property
    def projector(self) -> BuildFile | None:
        return next((f for f in self.files if f.role is FileRole.PROJECTOR), None)

    @property
    def runtime_name(self) -> str:
        """What this build is called once installed: its first weights file,
        without `.gguf`, which is the id llama-server's router reports."""
        return self.weights.path.rsplit("/", 1)[-1].removesuffix(".gguf")

    @property
    def footprint_bytes(self) -> int:
        """Everything that lands on disk and loads together."""
        return sum(f.size_bytes for f in self.files)

    @property
    def weights_bytes(self) -> int:
        return sum(f.size_bytes for f in self.files if f.role is FileRole.WEIGHTS)
