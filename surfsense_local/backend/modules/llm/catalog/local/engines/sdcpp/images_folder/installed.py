"""An installed image model as sd-server runs it: every file on its flag, the
model's defaults, and the flags the manifest pins.
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass

from modules.llm.catalog.local.build import BuildFile, FileRole
from modules.llm.catalog.local.engines.sdcpp.images_folder.landing import landing
from modules.llm.catalog.local.engines.sdcpp.launch import default_flags, file_flags
from modules.llm.catalog.local.engines.sdcpp.rows.catalog import image_catalog
from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import CuratedModel


@dataclass(frozen=True)
class InstalledImage:
    model_id: str
    label: str
    # Each file's flag and its path inside the images folder.
    files: tuple[tuple[str, str], ...]
    args: tuple[str, ...]

    @property
    def served_file(self) -> str:
        """The weights' file name, which sd-server reports it was launched on."""
        path = next(p for flag, p in self.files if flag in ("-m", "--diffusion-model"))
        return path.rsplit("/", 1)[-1]


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
            model = by_id[row.id]
            where = _where(installs.get(model_id))
            pinned = next(
                b
                for b in model.builds
                if b.quantization == build_row.build.quantization
            )
            return InstalledImage(
                model_id,
                row.name,
                file_flags(model.evidence.architecture, build_row.build, where),
                default_flags(model.image) + tuple(pinned.run.args),
            )
    return None


def _where(record: InstalledBuild | None) -> Callable[[BuildFile], str]:
    def where(file: BuildFile) -> str:
        # A download the old list made keeps the name it was saved as.
        if file.role is FileRole.WEIGHTS and record is not None:
            return record.weights[0]
        return landing(file)

    return where
