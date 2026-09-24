"""An installed image model as sd-server runs it: the recorded file and the flags
the manifest pins.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from modules.llm.catalog.local.engines.sdcpp.rows.catalog import image_catalog
from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import CuratedModel


@dataclass(frozen=True)
class InstalledImage:
    model_id: str
    label: str
    file: str
    args: tuple[str, ...]


def installed_image(
    model_id: str,
    models: Sequence[CuratedModel],
    installs: Mapping[str, InstalledBuild],
    files: Collection[str],
) -> InstalledImage | None:
    """The installed image build called `model_id`, or None."""
    by_id = {m.id: m for m in models}
    for row in image_catalog(models, installs, files, lambda _: ""):
        for build_row in row.builds:
            if build_row.installed_as != model_id:
                continue
            record = installs.get(model_id)
            file = (
                record.weights[0]
                if record
                else build_row.build.weights.path.rsplit("/", 1)[-1]
            )
            if file not in files:
                return None
            pinned = next(
                b
                for b in by_id[row.id].builds
                if b.quantization == build_row.build.quantization
            )
            return InstalledImage(model_id, row.name, file, tuple(pinned.run.args))
    return None
