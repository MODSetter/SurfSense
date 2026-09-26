"""Files the old hard-coded list downloaded, recorded as their curated builds: it
verified the same sha256. Recorded in place, since sd-server may hold them open.
"""

from collections.abc import Iterable, Sequence

from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import CuratedModel

# old filename -> (curated id, quantization). The old list's SDXL Turbo is not
# curated any more: its licence does not allow commercial use.
LEGACY_FILES = {
    "sd15-q4_0.gguf": ("stable-diffusion-1.5", "Q4_0"),
    "sdxl-base-q4_0.gguf": ("sdxl-base-1.0", "Q4_0"),
}


def adopt(files: Iterable[str], models: Sequence[CuratedModel]) -> list[InstalledBuild]:
    """An install record for each old file, as though it were installed today."""
    by_id = {m.id: m for m in models}
    records = []
    for name in files:
        if name not in LEGACY_FILES:
            continue
        model_id, quantization = LEGACY_FILES[name]
        model = by_id.get(model_id)
        build = (
            next((b for b in model.as_builds() if b.quantization == quantization), None)
            if model
            else None
        )
        if build is None:
            continue
        records.append(
            InstalledBuild(
                model_id=build.runtime_name,
                repo=build.weights.repo,
                revision=build.weights.revision,
                quantization=quantization,
                weights=(name,),
            )
        )
    return records
