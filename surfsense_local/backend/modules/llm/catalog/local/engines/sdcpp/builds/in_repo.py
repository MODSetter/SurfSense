"""Which files in a diffusion repo make a build: each root GGUF holding the UNet,
VAE and text encoder, which is what `sd-server -m` loads.
"""

from collections.abc import Iterable

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.listed_file import ListedFile
from modules.llm.catalog.local.quantization import quantization_label


def builds_in(
    listing: Iterable[ListedFile], *, repo: str = "", revision: str = "main"
) -> list[Build]:
    """Every GGUF at the repo's root as a build, smallest first."""
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
        if f.path.lower().endswith(".gguf") and "/" not in f.path
    ]
    return sorted(builds, key=lambda b: (b.footprint_bytes, b.quantization))
