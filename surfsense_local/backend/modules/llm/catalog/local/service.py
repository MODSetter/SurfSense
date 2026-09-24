"""The local catalog's side effects, across every engine: the machine, install
ids, and one install path. What differs per engine is behind `LocalEngine`."""

import asyncio
import secrets
import threading
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.audiocpp.engine import AudioCppEngine
from modules.llm.catalog.local.engines.engine import LocalEngine
from modules.llm.catalog.local.engines.llamacpp.engine import LlamaCppEngine
from modules.llm.catalog.local.engines.sdcpp.engine import SdCppEngine
from modules.llm.catalog.local.install import download
from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.install.tickets import TicketStore
from modules.llm.catalog.local.installs import forget_install
from modules.llm.catalog.local.manifest import LocalManifest
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.fit import HardwareBudget
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


@dataclass(frozen=True)
class Catalog:
    budget: HardwareBudget
    devices: tuple[Device, ...]
    # Beside the budget rather than in it: the budget is memory, this is a
    # diagnosis, and a broken install must not read as a machine without a card.
    gpu_status: GpuStatus
    rows: tuple[LocalRow, ...]
    recommended_id: str | None


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
        self._curated_ids: dict[str, tuple[Build, str]] = {}
        self._curated_tokens: dict[tuple[str, str], str] = {}
        # One pull at a time: two downloads compete for one disk and one bar.
        self._install_lock = asyncio.Lock()
        self.llamacpp = LlamaCppEngine(models_dir, runtime_url, self.budget)
        self.sdcpp = SdCppEngine(images_dir, manifest.models)
        self.audiocpp = AudioCppEngine(audio_dir, manifest.models)
        self._engines: tuple[LocalEngine, ...] = (
            self.llamacpp,
            self.sdcpp,
            self.audiocpp,
        )

    def install_lock(self) -> asyncio.Lock:
        return self._install_lock

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
                selected=selected.get(engine.model_type),
            )
        )
        star = next((row.id for row in rows if row.recommended), None)
        return Catalog(
            self.budget(), inventory.devices, inventory.gpu_status, rows, star
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

    async def repo(self, repo: str) -> tuple[LocalRow, bool]:
        """A searched repo's row, its builds installable through tickets."""
        return await self.llamacpp.repo(
            repo, lambda build, tag: self._tickets.mint(build, pipeline_tag=tag)
        )

    # installing -------------------------------------------------------------

    def resolve_install(self, catalog_id: str) -> InstallPlan | None:
        """An id from either origin as a build, or None once it has gone stale."""
        curated = self._curated_ids.get(catalog_id)
        if curated is not None:
            build, engine = curated
            return InstallPlan(build.runtime_name, build, engine)
        ticket = self._tickets.resolve(catalog_id)
        if ticket is None:
            return None
        # Search reaches llama.cpp's catalog only.
        return InstallPlan(
            ticket.build.runtime_name,
            ticket.build,
            self.llamacpp.name,
            needs_check=True,
            pipeline_tag=ticket.pipeline_tag,
        )

    async def check(self, plan: InstallPlan) -> InstallPlan:
        return await self.engine(plan.engine).check(plan)

    def install(self, plan: InstallPlan) -> AsyncIterator[DownloadProgress]:
        """Every file of the build into its engine's folder, then recorded."""
        return download.download_build(plan, self._folder(plan.engine))

    def remove(self, model_id: str, *, engine: str) -> None:
        """Delete a model's files, every part and its projector, and forget it."""
        folder = self._folder(engine)
        for name in forget_install(folder, model_id):
            (folder / name).unlink(missing_ok=True)
        self.engine(engine).after_remove()

    def _folder(self, engine: str) -> Path:
        folder = self.engine(engine).folder
        if folder is None:
            raise InstallRefusedError("This build of SurfSense cannot run this model.")
        return folder
