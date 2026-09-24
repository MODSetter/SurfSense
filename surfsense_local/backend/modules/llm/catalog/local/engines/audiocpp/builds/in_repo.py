"""Which files make an audio model's builds: each GGUF in the model's own folder
of a repo that holds several models, one file per build."""

from collections.abc import Iterable

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.catalog.local.quantization import quantization_label

# audio.cpp's name for a file kept in its source precision.
ORIGINAL = "orig"


def build_label(path: str) -> str:
    if path.lower().removesuffix(".gguf").endswith(f"-{ORIGINAL}"):
        return ORIGINAL
    return quantization_label(path)


def builds_in(
    listing: Iterable[ListedFile],
    folder: str,
    *,
    repo: str = "",
    revision: str = "main",
) -> list[Build]:
    """Every GGUF directly inside `folder` as a build."""
    return [
        Build(
            build_label(f.path),
            (
                BuildFile(
                    FileRole.WEIGHTS, f.path, f.size_bytes, f.sha256, repo, revision
                ),
            ),
        )
        for f in listing
        if f.path.lower().endswith(".gguf") and f.path.rsplit("/", 1)[0] == folder
    ]
