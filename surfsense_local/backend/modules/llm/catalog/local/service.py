"""The local catalog's side effects, across every engine: the machine, install
ids, and one install path. What differs per engine is behind `LocalEngine`."""

import asyncio
import secrets
import threading
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from modules.embedding.spec import EmbedderSpec
from modules.llm.activity import ModelFileHeldError
from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.audiocpp.audio_folder.espeak import Espeak
from modules.llm.catalog.local.engines.audiocpp.engine import AudioCppEngine
from modules.llm.catalog.local.engines.engine import LocalEngine
from modules.llm.catalog.local.engines.llamacpp.engine import LlamaCppEngine
from modules.llm.catalog.local.engines.llamacpp.manifest_fields import SamplingSet
from modules.llm.catalog.local.engines.llamacpp.models_folder.scan import (
    ProjectorNotice,
)
from modules.llm.catalog.local.engines.llamacpp.sampling import publisher_sampling
from modules.llm.catalog.local.engines.llamacpp.search.hits import SearchHit
from modules.llm.catalog.local.engines.onnxruntime.engine import OnnxRuntimeEngine
from modules.llm.catalog.local.engines.sdcpp.engine import SdCppEngine
from modules.llm.catalog.local.install import download
from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.catalog.local.install.disk_room import refuse_without_room
from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.install.tickets import TicketStore
from modules.llm.catalog.local.install_jobs.jobs import InstallJobs
from modules.llm.catalog.local.installs import (
    forget_install,
    install_files,
    read_installs,
)
from modules.llm.catalog.local.manifest import LocalManifest
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.catalog.local.search_cache import SearchCache
from modules.llm.fit import HardwareBudget, ModelShape
from modules.llm.hardware import (
    BudgetMode,
    Device,
    GpuStatus,
    SystemInventory,
    available_bytes,
    build_budget,
    os_reports_gpu,
    probe_devices,
    system_inventory,
)
from modules.llm.hardware.inventory import OsGpu, Probe
from modules.llm.model_type import ModelType
from modules.llm.providers.types import DownloadProgress
from shared.config import get_storage_settings


@dataclass(frozen=True)
class Catalog:
    budget: HardwareBudget
    devices: tuple[Device, ...]
    # Beside the budget rather than in it: the budget is memory, this is a
    # diagnosis, and a broken install must not read as a machine without a card.
    gpu_status: GpuStatus
    rows: tuple[LocalRow, ...]
    recommended_id: str | None
    projector_notices: tuple[ProjectorNotice, ...]


class LocalCatalogService:
    def __init__(
        self,
        manifest: LocalManifest,
        models_dir: Path,
        library_dir: Path,
        runtime_url: str = "http://127.0.0.1:8080",
        *,
        images_dir: Path | None = None,
        audio_dir: Path | None = None,
        audio_bundled_dir: Path | None = None,
        audio_espeak: Espeak | None = None,
        embeddings_dir: Path | None = None,
        probe: Probe = probe_devices,
        os_gpu: OsGpu = os_reports_gpu,
    ) -> None:
        self._manifest = manifest
        self._library_dir = library_dir
        self._probe = probe
        self._os_gpu = os_gpu
        self._inventory: SystemInventory | None = None
        # The startup warm and the first request race for this.
        self._inventory_lock = threading.Lock()
        self._tickets = TicketStore()
        self._search_cache = SearchCache()
        self._curated_ids: dict[str, tuple[Build, str]] = {}
        self._curated_tokens: dict[tuple[str, str], str] = {}
        # The shape each curated build was committed with, by the key an id is
        # minted on, so an install can be priced where the manifest is known.
        self._curated_shapes: dict[tuple[str, str], ModelShape | None] = {
            (build.weights.repo, build.weights.path): model.model_shape
            for model in manifest.models
            for build in model.as_builds()
        }
        # An embedder installs under its catalog id: every ONNX repo names its
        # weights model.onnx, so the file cannot name the install as a GGUF does.
        self._curated_entries: dict[tuple[str, str], str] = {
            (build.weights.repo, build.weights.path): model.id
            for model in manifest.models
            if model.embedding is not None
            for build in model.as_builds()
        }
        # One pull at a time: two downloads compete for one disk and one bar.
        self._install_lock = asyncio.Lock()
        self._install_jobs = InstallJobs(self._install_lock)
        self.llamacpp = LlamaCppEngine(models_dir, runtime_url, self.budget)
        self.sdcpp = SdCppEngine(images_dir, manifest.models)
        self.audiocpp = AudioCppEngine(
            audio_dir,
            manifest.models,
            bundled_dir=audio_bundled_dir,
            espeak=audio_espeak,
        )
        self.onnxruntime = OnnxRuntimeEngine(
            embeddings_dir or get_storage_settings().embedding_models_dir
        )
        self._engines: tuple[LocalEngine, ...] = (
            self.llamacpp,
            self.sdcpp,
            self.audiocpp,
            self.onnxruntime,
        )

    def install_lock(self) -> asyncio.Lock:
        return self._install_lock

    def install_jobs(self) -> InstallJobs:
        return self._install_jobs

    # the machine ------------------------------------------------------------

    def inventory(self) -> SystemInventory:
        """Probe once and remember, across every thread that asks. The first
        call compiles Metal shaders and costs about 19 seconds on a Mac."""
        with self._inventory_lock:
            if self._inventory is None:
                self._inventory = system_inventory(
                    self._library_dir, probe=self._probe, os_gpu=self._os_gpu
                )
            return self._inventory

    def devices(self) -> tuple[Device, ...]:
        return self.inventory().devices

    def budget(self, mode: BudgetMode = BudgetMode.CAPACITY) -> HardwareBudget:
        """Capacity by default: a catalog is a shelf, not a launch decision."""
        return build_budget(self.devices(), available_bytes(), mode=mode)

    def warm(self) -> None:
        """Probe, then let each engine settle its folder, off the first render."""
        self.inventory()
        for engine in self._engines:
            engine.on_startup()

    # engines ----------------------------------------------------------------

    def engine(self, name: str) -> LocalEngine:
        return next(e for e in self._engines if e.name == name)

    def engine_holding(self, model_id: str) -> LocalEngine | None:
        """The engine with an installed model called `model_id`, if any."""
        return next((e for e in self._engines if e.holds(model_id)), None)

    def engine_to_delete_from(self, model_id: str) -> LocalEngine | None:
        """The engine a delete of `model_id` belongs to: the one holding it, or
        the one whose record still names it after a delete that stopped part
        way, when no engine lists a build that is missing files."""
        return self.engine_holding(model_id) or next(
            (
                e
                for e in self._engines
                if e.folder is not None and model_id in read_installs(e.folder)
            ),
            None,
        )

    # the catalog ------------------------------------------------------------

    def catalog(self, selected: Mapping[ModelType, str] | None = None) -> Catalog:
        """`selected` names the installed model in use per type, so a row can
        lead with it."""
        selected = selected or {}
        inventory = self.inventory()
        rows = tuple(
            row
            for engine in self._engines
            for row in engine.rows(
                self._manifest.models,
                self._minter(engine.name),
                selected=next(
                    (selected[t] for t in engine.model_types if t in selected), None
                ),
            )
        )
        star = next((row.id for row in rows if row.recommended), None)
        return Catalog(
            self.budget(),
            inventory.devices,
            inventory.gpu_status,
            rows,
            star,
            self.llamacpp.projector_notices(),
        )

    def _minter(self, engine: str) -> Callable[[Build], str]:
        def mint(build: Build) -> str:
            """A stable opaque id per curated build, minted once per process,
            so the renderer cannot assemble one."""
            key = (build.weights.repo, build.weights.path)
            token = self._curated_tokens.get(key)
            if token is None:
                token = secrets.token_urlsafe(18)
                self._curated_tokens[key] = token
                self._curated_ids[token] = (build, engine)
            return token

        return mint

    async def search(self, query: str, *, limit: int = 30) -> list[SearchHit]:
        """Hugging Face search, answered from the cache inside its window.

        The router gates egress before calling, so a cached answer is never
        served while egress is off.
        """
        if (hits := self._search_cache.get(query, limit)) is not None:
            return hits
        hits = await self.llamacpp.search(query, limit=limit)
        self._search_cache.put(query, limit, hits)
        return hits

    async def repo(self, repo: str) -> tuple[LocalRow, bool]:
        """A searched repo's row, its builds installable through tickets."""
        return await self.llamacpp.repo(
            repo, lambda build, tag: self._tickets.mint(build, pipeline_tag=tag)
        )

    def publisher_sampling(
        self, model: str, reasoning: bool | None
    ) -> SamplingSet | None:
        """What a curated chat model's publisher set for this mode, else None."""
        return publisher_sampling(self._manifest.models, model, reasoning)

    # installing -------------------------------------------------------------

    def resolve_install(self, catalog_id: str) -> InstallPlan | None:
        """An id from either origin as a build, or None once it has gone stale."""
        curated = self._curated_ids.get(catalog_id)
        if curated is not None:
            build, engine = curated
            key = (build.weights.repo, build.weights.path)
            shape = self._curated_shapes.get(key)
            name = self._curated_entries.get(key, build.runtime_name)
            return InstallPlan(name, build, engine, shape=shape)
        ticket = self._tickets.resolve(catalog_id)
        if ticket is None:
            return None
        return InstallPlan(
            ticket.model_id or ticket.build.runtime_name,
            ticket.build,
            ticket.engine,
            needs_check=ticket.engine == self.llamacpp.name,
            pipeline_tag=ticket.pipeline_tag,
        )

    def offer_embedder(self, build: Build, spec: EmbedderSpec) -> str:
        """An install id for a Hugging Face embedder, its spec held for the
        checks after its download."""
        self.onnxruntime.offer(spec)
        return self._tickets.mint(build, engine=self.onnxruntime.name, model_id=spec.id)

    async def check(self, plan: InstallPlan) -> InstallPlan:
        """The engine's refusals first, then the disk's."""
        engine = self.engine(plan.engine)
        checked = await engine.check(plan)
        folder = self._folder(plan.engine)
        fetched = sum(
            f.size_bytes
            for f in checked.build.files
            if not (folder / engine.landing(f, checked.model_id)).exists()
        )
        refuse_without_room(folder, fetched)
        return checked

    def install(self, plan: InstallPlan) -> AsyncIterator[DownloadProgress]:
        """Every file of the build into its engine's folder, then recorded."""
        engine = self.engine(plan.engine)
        return download.download_build(
            plan,
            self._folder(plan.engine),
            lambda file: engine.landing(file, plan.model_id),
        )

    def remove(self, model_id: str, *, engine: str) -> None:
        """Delete a model's files, every part and its projector, and forget it.

        Files first: Windows refuses to delete one a server still has open, and
        a record dropped before that left the model unlisted with its files on
        disk."""
        folder = self._folder(engine)
        for name in install_files(folder, model_id):
            try:
                (folder / name).unlink(missing_ok=True)
            except PermissionError as error:
                raise ModelFileHeldError(model_id) from error
        forget_install(folder, model_id)
        self.engine(engine).after_remove()

    def _folder(self, engine: str) -> Path:
        folder = self.engine(engine).folder
        if folder is None:
            raise InstallRefusedError(
                "This build of SurfSense cannot run this model.", InstallCode.NO_ENGINE
            )
        return folder
