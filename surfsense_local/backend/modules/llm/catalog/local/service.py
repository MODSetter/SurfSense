"""The local catalog's side effects: the machine, the models folder, the network.

Everything that decides lives in pure modules beside this one; this reads the
disk and the hub, writes the preset and the install record, and hands the
results in. The catalog itself answers with no network and nothing to wait for.
"""

import asyncio
import logging
import secrets
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx

from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import Build, FileRole
from modules.llm.catalog.local.engines.llamacpp.rows.catalog import LocalCatalog, local_catalog
from modules.llm.catalog.local.engines.llamacpp.models_folder.scan import DownloadedModel, scan
from modules.llm.catalog.local.installs import (
    InstalledBuild,
    forget_install,
    projector_filename,
    read_installs,
    record_install,
)
from modules.llm.catalog.local.manifest import LocalManifest
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.catalog.local.engines.llamacpp.search.exact_check import check_build
from modules.llm.catalog.local.engines.llamacpp.search.hits import SearchHit, search_models
from modules.llm.catalog.local.engines.llamacpp.search.listing import read_listing
from modules.llm.catalog.local.engines.llamacpp.search.repo_row import repo_row
from modules.llm.catalog.local.engines.llamacpp.search.tickets import TicketStore
from modules.llm.catalog.local.engines.llamacpp.support import (
    projector_fits_model,
    projector_reads_images,
)
from modules.llm.fit import FitState, HardwareBudget, plan_load
from modules.llm.hardware import (
    BudgetMode,
    Device,
    GpuStatus,
    SystemInventory,
    available_bytes,
    build_budget,
    fit_target_mib,
    os_reports_gpu,
    probe_devices,
    system_inventory,
)
from modules.llm.hardware.inventory import OsGpu, Probe
from modules.llm.model_type import ModelType
from modules.llm.providers.llamacpp import (
    PRESET_FILE,
    PROVIDER,
    LoadProgress,
    ModelPreset,
    RouterClient,
    download_gguf,
    warm_model,
    write_presets,
)
from modules.llm.providers.types import DownloadProgress

logger = logging.getLogger(__name__)

RESOLVE = "https://huggingface.co/{repo}/resolve/{revision}/{path}"


class InstallRefusedError(Exception):
    """A build the exact check turned down, with the sentence a person reads."""


@dataclass(frozen=True)
class InstallPlan:
    """A resolved build, named by the server rather than by the renderer."""

    model_id: str
    build: Build
    # A searched build is read exactly before it downloads; a curated one was
    # read when the manifest was refreshed.
    needs_check: bool
    pipeline_tag: str | None = None


@dataclass(frozen=True)
class Catalog:
    budget: HardwareBudget
    devices: tuple[Device, ...]
    # Beside the budget rather than in it: the budget is memory, this is a
    # diagnosis, and a broken install must not read as a machine without a card.
    gpu_status: GpuStatus
    local: LocalCatalog


def runtime_name(build: Build) -> str:
    """What the runtime will call this build once it is on disk."""
    return build.weights.path.rsplit("/", 1)[-1].removesuffix(".gguf")


class LocalCatalogService:
    def __init__(
        self,
        manifest: LocalManifest,
        models_dir: Path,
        library_dir: Path,
        runtime_url: str = "http://127.0.0.1:8080",
        *,
        probe: Probe = probe_devices,
        os_gpu: OsGpu = os_reports_gpu,
    ) -> None:
        self._manifest = manifest
        self._models_dir = models_dir
        self._library_dir = library_dir
        self._runtime_url = runtime_url
        self._probe = probe
        self._os_gpu = os_gpu
        self._inventory: SystemInventory | None = None
        # The startup warm and the first request race for this.
        self._inventory_lock = threading.Lock()
        self._tickets = TicketStore()
        self._curated_ids: dict[str, Build] = {}
        self._curated_tokens: dict[tuple[str, str], str] = {}
        # One pull at a time: two downloads compete for one disk and one bar.
        self._install_lock = asyncio.Lock()

    provider_name = PROVIDER

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
        """Probe and write the preset off the path of the first render."""
        self.inventory()
        self.reprice()

    # the catalog ------------------------------------------------------------

    def catalog(self, *, selected: str | None = None) -> Catalog:
        """`selected` is the runtime's name for the model in use, so a row can
        lead with it."""
        inventory = self.inventory()
        budget = self.budget()
        local = local_catalog(
            self._manifest.models,
            self.installed(),
            budget,
            self._curated_id,
            selected=selected,
        )
        return Catalog(budget, inventory.devices, inventory.gpu_status, local)

    def installed(self) -> list[DownloadedModel]:
        """The models on disk, read from their own headers."""
        return scan(self._models_dir, read_installs(self._models_dir))

    def _curated_id(self, build: Build) -> str:
        """A stable opaque id per curated build, minted once per process, so the
        renderer cannot assemble one."""
        key = (build.weights.repo, build.weights.path)
        token = self._curated_tokens.get(key)
        if token is None:
            token = secrets.token_urlsafe(18)
            self._curated_tokens[key] = token
            self._curated_ids[token] = build
        return token

    # search -----------------------------------------------------------------

    async def search(self, query: str, *, limit: int = 30) -> list[SearchHit]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await search_models(client, query, limit=limit)

    async def repo(self, repo: str) -> tuple[LocalRow, bool]:
        """One repo's builds from its listing, and whether it needs an account."""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            listing = await read_listing(client, repo)

        def mint(build: Build) -> str:
            return self._tickets.mint(build, pipeline_tag=listing.pipeline_tag)

        return repo_row(listing, self.budget(), mint), listing.gated

    # installing -------------------------------------------------------------

    def resolve_install(self, catalog_id: str) -> InstallPlan | None:
        """An id from either origin as a build, or None once it has gone stale."""
        build = self._curated_ids.get(catalog_id)
        if build is not None:
            return InstallPlan(runtime_name(build), build, needs_check=False)
        ticket = self._tickets.resolve(catalog_id)
        if ticket is None:
            return None
        return InstallPlan(
            runtime_name(ticket.build), ticket.build, True, ticket.pipeline_tag
        )

    async def check(self, plan: InstallPlan) -> InstallPlan:
        """Read a searched build's headers and refuse what cannot run, before any
        bytes move. Returns the plan with a failed projector dropped."""
        if not plan.needs_check:
            return plan
        async with httpx.AsyncClient(follow_redirects=True) as client:
            checked = await check_build(
                client, plan.build, plan.pipeline_tag, self.budget()
            )
        if not checked.is_model:
            raise InstallRefusedError("This file is not a model SurfSense can run.")
        if ModelType.TEXT_GEN not in checked.classification.types:
            raise InstallRefusedError(
                checked.classification.reason or "SurfSense cannot run this model."
            )
        if checked.fit.state is FitState.TOO_BIG:
            raise InstallRefusedError(
                "This build is too big for this computer. Pick a smaller one."
            )
        return InstallPlan(plan.model_id, checked.build, False, plan.pipeline_tag)

    async def install(self, plan: InstallPlan) -> AsyncIterator[DownloadProgress]:
        """Fetch every file of the build, pinned and verified, then record it.

        Weights keep their own names; a projector is saved under the model's
        name, so two vision models never share or overwrite one.
        """
        total = plan.build.footprint_bytes
        done = 0
        weights: list[str] = []
        projector: str | None = None
        for file in plan.build.files:
            if file.role is FileRole.PROJECTOR:
                name = projector_filename(plan.model_id)
                projector = name
            else:
                name = file.path.rsplit("/", 1)[-1]
                weights.append(name)
            url = RESOLVE.format(repo=file.repo, revision=file.revision, path=file.path)
            finished = 0
            async for step in download_gguf(
                url, self._models_dir / name, sha256=file.sha256
            ):
                finished = step.completed
                yield DownloadProgress(
                    step.status, done + step.completed, max(total, done + step.total)
                )
            done += finished
        weights_file = plan.build.weights
        projector_file = plan.build.projector
        record_install(
            self._models_dir,
            InstalledBuild(
                model_id=plan.model_id,
                repo=weights_file.repo,
                revision=weights_file.revision,
                quantization=plan.build.quantization,
                weights=tuple(weights),
                projector=projector,
                projector_gguf=dict(projector_file.gguf) if projector_file else {},
            ),
        )

    def remove(self, model_id: str) -> None:
        """Delete a model's files, every part and its projector, and forget it."""
        for name in forget_install(self._models_dir, model_id):
            (self._models_dir / name).unlink(missing_ok=True)

    # the runtime ------------------------------------------------------------

    def reprice(self) -> None:
        """Write the preset for everything on disk.

        The router reads its folder and this file once, at startup, so writing it
        is what makes a finished download reachable: Electron watches the file and
        restarts the sidecar. Capacity decides the verdict, so the plan agrees
        with the badge; live caps how far the window widens past the floor.
        """
        budget = self.budget(BudgetMode.CAPACITY)
        live = self.budget(BudgetMode.LIVE)
        presets = []
        for model in self.installed():
            if model.shape is None:
                # Unreadable: skipping costs this model, failing would leave the
                # runtime dead over a file nobody asked it to load.
                logger.warning("skipping unreadable model %s", model.path.name)
                continue
            projector = model.projector if _pairs(model) else None
            mmproj_bytes = projector.stat().st_size if projector else 0
            plan = plan_load(
                model.shape,
                model.weights_bytes,
                budget,
                live=live,
                mmproj_bytes=mmproj_bytes,
            )
            presets.append(
                ModelPreset(
                    model_id=model.model_id,
                    path=str(model.path),
                    n_ctx=plan.n_ctx,
                    precision=plan.precision,
                    fit_target_mib=fit_target_mib(mmproj_bytes),
                    mmproj_path=str(projector) if projector else None,
                )
            )
        write_presets(self._models_dir / PRESET_FILE, presets)

    async def wait_until_servable(
        self, model_id: str, *, timeout: float = 30.0, interval: float = 0.5
    ) -> bool:
        """Block until the restarted router lists the model. False on timeout:
        the download succeeded, and the model is usable once the sidecar is back."""
        deadline = time.monotonic() + timeout
        client = RouterClient(self._runtime_url)
        while time.monotonic() < deadline:
            try:
                if any(m.id == model_id for m in await client.models()):
                    return True
            except httpx.HTTPError:
                pass  # restarting, which is exactly what we are waiting for
            await asyncio.sleep(interval)
        return False

    def warm_model(self, model_id: str) -> AsyncIterator[LoadProgress]:
        """Load a model now, so the first question does not pay a cold load."""
        return warm_model(self._runtime_url, model_id)


def _pairs(model: DownloadedModel) -> bool:
    """The recorded or name-matched projector, only when it sees and fits."""
    return (
        model.projector is not None
        and projector_reads_images(model.projector_kv)
        and projector_fits_model(model.projector_kv, model.model_kv)
    )
