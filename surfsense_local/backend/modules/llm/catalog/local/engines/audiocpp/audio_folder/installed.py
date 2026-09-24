"""The installed audio models as audio.cpp's server loads them: the recorded
file and the family the manifest names, which is what the server dispatches on.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from modules.llm.catalog.local.engines.audiocpp.manifest_fields import AudioDefaults
from modules.llm.catalog.local.engines.audiocpp.rows.catalog import audio_catalog
from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import CuratedModel


@dataclass(frozen=True)
class InstalledAudio:
    model_id: str
    # The manifest entry it is a build of.
    entry: str
    family: str
    file: str
    # Its voices, languages and measured memory, from the manifest entry.
    audio: AudioDefaults


def installed_audio(
    models: Sequence[CuratedModel],
    installs: Mapping[str, InstalledBuild],
    files: Collection[str],
) -> list[InstalledAudio]:
    """Every installed audio build, in the manifest's order."""
    by_id = {m.id: m for m in models}
    return [
        InstalledAudio(
            build.installed_as,
            row.id,
            by_id[row.id].evidence.architecture,
            installs[build.installed_as].weights[0],
            by_id[row.id].audio,  # type: ignore[arg-type]  # an audio row's entry has one
        )
        for row in audio_catalog(models, installs, files, lambda _: "")
        for build in row.builds
        if build.installed_as is not None
    ]
