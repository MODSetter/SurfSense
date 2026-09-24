"""sd.cpp behind the engine seam: image models in sd-server's folder."""

from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.engine import InstallStep
from modules.llm.catalog.local.engines.sdcpp import ENGINE
from modules.llm.catalog.local.engines.sdcpp.images_folder.files import files_in
from modules.llm.catalog.local.engines.sdcpp.images_folder.installed import (
    InstalledImage,
    installed_image,
)
from modules.llm.catalog.local.engines.sdcpp.images_folder.legacy import adopt
from modules.llm.catalog.local.engines.sdcpp.rows.catalog import image_catalog
from modules.llm.catalog.local.install.plan import InstallPlan
from modules.llm.catalog.local.installs import read_installs, record_install
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.model_type import ModelType
from modules.llm.providers.sdcpp import PROVIDER


class SdCppEngine:
    name = ENGINE
    model_type = ModelType.IMAGE_GEN
    provider = PROVIDER

    def __init__(self, images_dir: Path | None, models: Sequence[CuratedModel]) -> None:
        # None where Electron staged no sd-server: nothing is offered.
        self._images_dir = images_dir
        self._models = models

    @property
    def folder(self) -> Path | None:
        return self._images_dir

    def rows(
        self,
        models: Sequence[CuratedModel],
        mint: Callable[[Build], str],
        *,
        selected: str | None,
    ) -> tuple[LocalRow, ...]:
        if self._images_dir is None:
            return ()
        return tuple(
            image_catalog(
                models,
                read_installs(self._images_dir),
                files_in(self._images_dir),
                mint,
                selected=selected,
            )
        )

    def installed_image(self, model_id: str) -> InstalledImage | None:
        """The installed image model called `model_id`, as sd-server runs it."""
        if self._images_dir is None:
            return None
        return installed_image(
            model_id,
            self._models,
            read_installs(self._images_dir),
            files_in(self._images_dir),
        )

    def holds(self, model_id: str) -> bool:
        return self.installed_image(model_id) is not None

    async def check(self, plan: InstallPlan) -> InstallPlan:
        return plan  # curated only: read when the manifest was refreshed

    async def after_install(self, model_id: str) -> AsyncIterator[InstallStep]:
        # sd-server takes its model at launch, from the selection: nothing to
        # restart and nothing to warm.
        yield InstallStep("complete", "Model is ready")

    def after_remove(self) -> None:
        pass

    def on_startup(self) -> None:
        """Record image models the old hard-coded list downloaded, once."""
        if self._images_dir is None:
            return
        recorded = read_installs(self._images_dir)
        taken = {name for r in recorded.values() for name in r.files}
        loose = [f for f in files_in(self._images_dir) if f not in taken]
        for record in adopt(loose, self._models):
            if record.model_id not in recorded:
                record_install(self._images_dir, record)
