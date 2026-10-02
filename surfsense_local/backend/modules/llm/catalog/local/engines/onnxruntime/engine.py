"""onnxruntime behind the engine seam: embedders, one folder each, run in process.

There is no server to configure: the encoder loads whichever model the active
index names. bge is shipped in the read-only models pack and never downloaded.
"""

import asyncio
import shutil
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

from modules.embedding.bundled import BGE, bundled_dir
from modules.embedding.encoder import missing_files
from modules.embedding.spec import EmbedderSpec
from modules.embedding.verify import verify
from modules.llm.catalog.local.build import Build, BuildFile
from modules.llm.catalog.local.engines.engine import InstallStep
from modules.llm.catalog.local.engines.onnxruntime import ENGINE
from modules.llm.catalog.local.engines.onnxruntime.rows import (
    downloaded_rows,
    embedding_catalog,
)
from modules.llm.catalog.local.install.plan import InstallPlan
from modules.llm.catalog.local.installs import (
    forget_install,
    install_files,
    read_installs,
)
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.model_type import ModelType

# Beside a Hugging Face pick's files: the spec its checks settled.
SPEC_FILE = "spec.json"


class OnnxRuntimeEngine:
    name = ENGINE
    model_types = (ModelType.EMBEDDING,)
    # Never a selection: the index names the embedder, not `selected_models`.
    provider = ENGINE

    def __init__(self, folder: Path) -> None:
        self._folder = folder
        # Hugging Face picks opened this session, by install name: their checks
        # run after the download, before the spec is kept beside the files.
        self._offered: dict[str, EmbedderSpec] = {}

    def offer(self, spec: EmbedderSpec) -> None:
        self._offered[spec.id] = spec

    def installed_spec(self, model_id: str) -> EmbedderSpec | None:
        """A downloaded Hugging Face pick's spec, as its checks left it."""
        path = self._folder / model_id / SPEC_FILE
        if not self.holds(model_id) or not path.is_file():
            return None
        return EmbedderSpec.model_validate_json(path.read_text())

    @property
    def folder(self) -> Path:
        return self._folder

    def rows(
        self,
        models: Sequence[CuratedModel],
        mint: Callable[[Build], str],
        *,
        selected: str | None,
    ) -> tuple[LocalRow, ...]:
        installs = read_installs(self._folder) if self._folder.is_dir() else {}
        picked = [
            spec
            for model_id in installs
            if (spec := self.installed_spec(model_id)) is not None
        ]
        return tuple(
            embedding_catalog(
                models,
                installs,
                mint,
                bundled={BGE.id} if self._ships_bge() else set(),
            )
        ) + tuple(downloaded_rows(picked))

    def landing(self, file: BuildFile, model_id: str) -> str:
        # Every ONNX repo calls its weights model.onnx: the folder tells them apart.
        return f"{model_id}/{file.name}"

    def holds(self, model_id: str) -> bool:
        if model_id == BGE.id and self._ships_bge():
            return True
        installs = read_installs(self._folder) if self._folder.is_dir() else {}
        return model_id in installs and not installs[model_id].pending

    def bundled(self, model_id: str) -> bool:
        return model_id == BGE.id and self._ships_bge()

    def _ships_bge(self) -> bool:
        return bundled_dir().is_dir() and not missing_files(BGE)

    async def check(self, plan: InstallPlan) -> InstallPlan:
        return plan  # curated only: checked when the manifest was refreshed

    async def after_install(self, model_id: str) -> AsyncIterator[InstallStep]:
        # Nothing to start: the encoder loads it when the index names it. A
        # Hugging Face pick is checked first, since nobody measured it.
        offered = self._offered.pop(model_id, None)
        if offered is not None:
            yield InstallStep("verifying", "Checking that it finds answers")
            width, refusal = await asyncio.to_thread(verify, offered)
            if refusal is not None:
                self._discard(model_id)
                yield InstallStep("error", refusal)
                return
            checked = offered.model_copy(update={"dimension": width})
            (self._folder / model_id / SPEC_FILE).write_text(checked.model_dump_json())
        yield InstallStep("complete", "Model is ready")

    def _discard(self, model_id: str) -> None:
        for name in install_files(self._folder, model_id):
            (self._folder / name).unlink(missing_ok=True)
        forget_install(self._folder, model_id)
        shutil.rmtree(self._folder / model_id, ignore_errors=True)

    def after_remove(self) -> None:
        """A removed model's folder still holds its spec: drop the folders no
        install names any more."""
        installs = read_installs(self._folder) if self._folder.is_dir() else {}
        for folder in self._folder.iterdir() if self._folder.is_dir() else ():
            if folder.is_dir() and folder.name not in installs:
                shutil.rmtree(folder, ignore_errors=True)

    def on_startup(self) -> None:
        pass
