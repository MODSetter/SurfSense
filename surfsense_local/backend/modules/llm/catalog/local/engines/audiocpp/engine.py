"""audio.cpp behind the engine seam: audio models in its server's folder."""

from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.audiocpp import ENGINE
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
from modules.llm.catalog.local.installs import read_installs
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.model_type import ModelType
from modules.llm.providers.audiocpp import PROVIDER


class AudioCppEngine:
    name = ENGINE
    model_type = ModelType.AUDIO_GEN
    provider = PROVIDER

    def __init__(self, audio_dir: Path | None, models: Sequence[CuratedModel]) -> None:
        # None where Electron staged no audio.cpp: nothing is offered.
        self._audio_dir = audio_dir
        self._models = models

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
        return tuple(
            audio_catalog(
                models,
                read_installs(self._audio_dir),
                files_in(self._audio_dir),
                mint,
                selected=selected,
            )
        )

    def installed(self) -> list[InstalledAudio]:
        if self._audio_dir is None:
            return []
        return installed_audio(
            self._models, read_installs(self._audio_dir), files_in(self._audio_dir)
        )

    def holds(self, model_id: str) -> bool:
        return self.installed_model(model_id) is not None

    def installed_model(self, model_id: str) -> InstalledAudio | None:
        return next((m for m in self.installed() if m.model_id == model_id), None)

    async def check(self, plan: InstallPlan) -> InstallPlan:
        return plan  # curated only: read when the manifest was refreshed

    async def after_install(self, model_id: str) -> AsyncIterator[InstallStep]:
        # Electron restarts the server on the new file; the model loads on its
        # first request, so there is nothing to wait for here.
        self._write_config()
        yield InstallStep("complete", "Model is ready")

    def _write_config(self) -> None:
        if self._audio_dir is not None:
            write_server_config(self._audio_dir, self.installed())

    def after_remove(self) -> None:
        self._write_config()

    def on_startup(self) -> None:
        """Write the config from what is installed, so a stale one heals."""
        self._write_config()
