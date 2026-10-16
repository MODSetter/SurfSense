"""The installed speech recognisers as the transcription server loads them:
the recorded file, the family the manifest names, and its reviewed languages."""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from modules.llm.catalog.local.engines.audiocpp.manifest_fields import (
    TranscriptionDefaults,
)
from modules.llm.catalog.local.engines.audiocpp.rows.catalog import audio_catalog
from modules.llm.catalog.local.installs import InstalledBuild
from modules.llm.catalog.local.manifest import CuratedModel


@dataclass(frozen=True)
class InstalledRecogniser:
    model_id: str
    # The manifest entry it is a build of.
    entry: str
    family: str
    path: Path
    # Its languages, locales, request options and measured memory.
    transcription: TranscriptionDefaults


def installed_recognisers(
    models: Sequence[CuratedModel],
    installs: Mapping[str, InstalledBuild],
    files: Collection[str],
    folder: Path,
) -> list[InstalledRecogniser]:
    """Every recogniser build installed in `folder`, in the manifest's order.
    None ships with the app, so only the audio folder holds one."""
    by_id = {m.id: m for m in models}
    return [
        InstalledRecogniser(
            build.installed_as,
            row.id,
            by_id[row.id].evidence.architecture,
            folder / installs[build.installed_as].weights[0],
            transcription,
        )
        for row in audio_catalog(models, installs, files, lambda _: "")
        if (transcription := by_id[row.id].transcription) is not None
        for build in row.builds
        if build.installed_as is not None
    ]
