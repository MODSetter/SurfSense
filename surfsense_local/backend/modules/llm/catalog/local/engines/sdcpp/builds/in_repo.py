"""Which files in a diffusion repo make a build: each GGUF at the repo's root, or
in the one folder an entry names, as a build of its own. Companions are added
by the entry, from their own repos.
"""

from collections.abc import Iterable

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.catalog.local.quantization import quantization_label


def builds_in(
    listing: Iterable[ListedFile],
    *,
    repo: str = "",
    revision: str = "main",
    folder: str = "",
) -> list[Build]:
    """Every GGUF directly in `folder`, the root by default, as a build,
    smallest first: a repo holding two conversions keeps one per folder."""
    builds = [
        Build(
            quantization_label(f.path),
            (
                BuildFile(
                    FileRole.WEIGHTS, f.path, f.size_bytes, f.sha256, repo, revision
                ),
            ),
        )
        for f in listing
        if f.path.lower().endswith(".gguf") and f.path.rpartition("/")[0] == folder
    ]
    return sorted(builds, key=lambda b: (b.footprint_bytes, b.quantization))
