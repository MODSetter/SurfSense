"""One row of a Hugging Face repo listing: what every engine picks builds from."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ListedFile:
    """One row of a repo listing."""

    path: str
    size_bytes: int
    sha256: str | None = None
