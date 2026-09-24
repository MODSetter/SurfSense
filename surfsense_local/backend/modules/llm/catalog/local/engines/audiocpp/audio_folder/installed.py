"""The installed audio models as audio.cpp's server loads them: the recorded
file and the family the manifest names, which is what the server dispatches on.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from modules.llm.catalog.local.engines.audiocpp.rows.catalog import audio_catalog
from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import CuratedModel


@dataclass(frozen=True)
class InstalledAudio:
    model_id: str
    family: str
    file: str


def installed_audio(
    models: Sequence[CuratedModel],
    installs: Mapping[str, InstalledBuild],
    files: Collection[str],
) -> list[InstalledAudio]:
    """Every installed audio build, in the manifest's order."""
    families = {m.id: m.evidence.architecture for m in models}
    return [
        InstalledAudio(
            build.installed_as,
            families[row.id],
            installs[build.installed_as].weights[0],
        )
        for row in audio_catalog(models, installs, files, lambda _: "")
        for build in row.builds
        if build.installed_as is not None
    ]
