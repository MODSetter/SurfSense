"""What one repo looked like at one commit: the input the assembly reads."""

from dataclasses import dataclass
from typing import Any

from modules.llm.catalog.local.builds import ListedFile


@dataclass(frozen=True)
class RepoAtRevision:
    repo: str
    revision: str
    pipeline_tag: str | None
    listing: tuple[ListedFile, ...]
    # The repo's machine-readable `params` file, where one exists.
    params: dict[str, Any] | None
