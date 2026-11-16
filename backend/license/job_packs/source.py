"""Where published packs are read from: the store's interface, which every store keeps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class PackAsset:
    """One published zip: its name, and a ref that changes whenever its bytes could."""

    name: str
    ref: str
    size: int
    # Where the store reads it from; an API address is not for the logs.
    locator: str = field(repr=False)


class PackSourceError(RuntimeError):
    """The store could not be read this time. Its message never holds a credential."""


class PackSource(Protocol):
    async def assets(self) -> list[PackAsset]: ...

    async def read(self, asset: PackAsset) -> bytes: ...
