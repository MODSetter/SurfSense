"""audio.cpp behind the engine seam: audio models in its server's folder."""

from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.audiocpp import ENGINE
from modules.llm.catalog.local.engines.audiocpp.audio_folder.espeak import Espeak
from modules.llm.catalog.local.engines.audiocpp.audio_folder.files import files_in
from modules.llm.catalog.local.engines.audiocpp.audio_folder.installed import (
    InstalledAudio,
    installed_audio,
)
from modules.llm.catalog.local.engines.audiocpp.audio_folder.server_config import (
    write_server_config,
)
from modules.llm.catalog.local.engines.audiocpp.rows.catalog import audio_catalog
from modules.llm.catalog.local.engines.engine import InstallStep
from modules.llm.catalog.local.install.plan import InstallPlan
from modules.llm.catalog.local.installs import InstalledBuild, read_installs
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.model_type import ModelType
from modules.llm.providers.audiocpp import PROVIDER
from modules.llm.providers.audiocpp.memory import OtherModel


class AudioCppEngine:
    name = ENGINE
    model_type = ModelType.AUDIO_GEN
    provider = PROVIDER

    def __init__(
        self,
        audio_dir: Path | None,
        models: Sequence[CuratedModel],
        *,
        bundled_dir: Path | None = None,
        espeak: Espeak | None = None,
    ) -> None:
        # None where Electron staged no audio.cpp: nothing is offered.
        self._audio_dir = audio_dir
        self._models = models
        # The models pack's voice, read in place.
        self._bundled_dir = bundled_dir
        self._espeak = espeak

    @property
    def folder(self) -> Path | None:
        return self._audio_dir

    def rows(
        self,
        models: Sequence[CuratedModel],
        mint: Callable[[Build], str],
        *,
        selected: str | None,
    ) -> tuple[LocalRow, ...]:
        if self._audio_dir is None:
            return ()
        bundled = self._bundled_installs()
        # A download of the same build wins: its Delete then removes the copy.
        downloaded = read_installs(self._audio_dir)
        return tuple(
            audio_catalog(
                models,
                {**bundled, **downloaded},
                files_in(self._audio_dir) | files_in(self._bundled_dir),
                mint,
                selected=selected,
                bundled=set(bundled) - set(downloaded),
            )
        )

    def _bundled_installs(self) -> dict[str, InstalledBuild]:
        if self._bundled_dir is None or not self._bundled_dir.is_dir():
            return {}
        return read_installs(self._bundled_dir)

    def installed(self) -> list[InstalledAudio]:
        """The audio folder's downloads, then the pack's voice unless downloaded."""
        if self._audio_dir is None:
            return []
        downloaded = installed_audio(
            self._models,
            read_installs(self._audio_dir),
            files_in(self._audio_dir),
            self._audio_dir,
        )
        if self._bundled_dir is None:
            return downloaded
        ids = {m.model_id for m in downloaded}
        bundled = installed_audio(
            self._models,
            self._bundled_installs(),
            files_in(self._bundled_dir),
            self._bundled_dir,
            bundled=True,
        )
        return downloaded + [m for m in bundled if m.model_id not in ids]

    def holds(self, model_id: str) -> bool:
        return self.installed_model(model_id) is not None

    def bundled(self, model_id: str) -> bool:
        model = self.installed_model(model_id)
        return model is not None and model.bundled

    def installed_model(self, model_id: str) -> InstalledAudio | None:
        return next((m for m in self.installed() if m.model_id == model_id), None)

    def others_than(self, model: InstalledAudio) -> tuple[OtherModel, ...]:
        """Every other curated audio model, most preferred first."""
        return tuple(
            OtherModel(m.name, m.audio.peak_mb)
            for m in self._models
            if m.audio is not None and m.id != model.entry
        )

    async def check(self, plan: InstallPlan) -> InstallPlan:
        return plan  # curated only: read when the manifest was refreshed

    async def after_install(self, model_id: str) -> AsyncIterator[InstallStep]:
        # Electron restarts the server on the new file; the model loads on its
        # first request, so there is nothing to wait for here.
        self._write_config()
        yield InstallStep("complete", "Model is ready")

    def _write_config(self) -> None:
        if self._audio_dir is not None:
            write_server_config(self._audio_dir, self.installed(), self._espeak)

    def after_remove(self) -> None:
        self._write_config()

    def on_startup(self) -> None:
        """Write the config from what is installed, so a stale one heals."""
        self._write_config()
