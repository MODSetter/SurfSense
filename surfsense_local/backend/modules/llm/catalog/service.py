"""Assembling what the model screen shows.

A new service rather than a parameter on the old one. `CatalogService` requires
an advisor and a scan; this tier has neither, and making one class serve both
would keep the scan-shaped vocabulary alive to describe something that no longer
scans.

Curated and installed are assembled from the manifest and the models directory,
both local, so this answers with **no network** and nothing to wait for.
"""

import asyncio
import logging
import secrets
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx

from modules.llm.catalog.manifest import CuratedModelsManifest
from modules.llm.catalog.recommendation import recommend
from modules.llm.catalog.rows import CatalogRow, curated_rows
from modules.llm.catalog.search import (
    SearchHit,
    TicketStore,
    is_supported,
    list_builds,
    search_models,
)
from modules.llm.fit import HardwareBudget, badge, estimate, plan_load
from modules.llm.gguf import shape_from_file, shape_from_url
from modules.llm.hardware import (
    BudgetMode,
    Device,
    available_bytes,
    build_budget,
    probe_devices,
)
from modules.llm.providers.llamacpp import (
    PRESET_FILE,
    PROVIDER,
    ModelPreset,
    RouterClient,
    download_gguf,
    write_presets,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstalledRow:
    """A model already on disk, named as the router reports it."""

    model_id: str
    file: str
    size_bytes: int


@dataclass(frozen=True)
class InstallPlan:
    """A resolved build, named by the server rather than by the renderer."""

    model_id: str
    repo: str
    file: str
    size_bytes: int


@dataclass(frozen=True)
class Catalog:
    budget: HardwareBudget
    devices: tuple[Device, ...]
    curated: tuple[CatalogRow, ...]
    installed: tuple[InstalledRow, ...]
    recommended_model_id: str | None


class CatalogService:
    """Curated plus installed, priced against this machine, offline."""

    def __init__(
        self,
        manifest: CuratedModelsManifest,
        models_dir: Path,
        library_dir: Path,
        runtime_url: str = "http://127.0.0.1:8080",
    ) -> None:
        self._runtime_url = runtime_url
        self._manifest = manifest
        self._models_dir = models_dir
        self._library_dir = library_dir
        self._devices: tuple[Device, ...] | None = None
        self._tickets = TicketStore()
        self._catalog_ids: dict[str, tuple[str, str]] = {}
        # One pull at a time: two concurrent downloads compete for the same disk
        # and the screen has one progress bar.
        self._install_lock = asyncio.Lock()

    provider_name = PROVIDER

    def install_lock(self) -> asyncio.Lock:
        return self._install_lock

    def catalog_id(self, row: CatalogRow) -> str:
        """A stable opaque id for a curated row, minted once per process.

        Opaque so the renderer cannot assemble one, which is the same reason
        searched builds get tickets rather than repo and file.
        """
        key = (row.variant.repo, row.variant.file)
        for token, existing in self._catalog_ids.items():
            if existing == key:
                return token
        token = secrets.token_urlsafe(18)
        self._catalog_ids[token] = key
        return token

    def reprice(self) -> None:
        """Write the preset for everything now on disk.

        The router reads its models directory, and this file, once at startup.
        Measured: a model dropped into a running router's directory is still
        invisible 26 seconds later and appears immediately after a restart. So
        writing this is what makes a completed download reachable: Electron
        watches the file and restarts the sidecar, which costs 0.15s because an
        idle router holds no model memory.

        Two budgets, because they answer different questions. Capacity decides
        the verdict, so the plan agrees with the badge the catalog showed. Live
        caps how far the window widens past the floor, because that part is
        opportunistic and on unified memory it comes out of the same pool the OS
        is using.
        """
        budget = self.budget(BudgetMode.CAPACITY)
        live = self.budget(BudgetMode.LIVE)
        presets = []
        for path in sorted(self._models_dir.glob("*.gguf")):
            try:
                shape = shape_from_file(path)
            except (OSError, ValueError):
                # A truncated or foreign file in the directory. Skipping it
                # costs that one model; failing would leave the runtime dead
                # over a file nobody asked it to load.
                logger.warning("skipping unreadable model %s", path.name)
                continue
            plan = plan_load(shape, path.stat().st_size, budget, live=live)
            presets.append(
                ModelPreset(path.stem, str(path), plan.n_ctx, plan.precision)
            )
        write_presets(self._models_dir / PRESET_FILE, presets)

    def resolve_install(self, catalog_id: str) -> InstallPlan | None:
        """Turn an id from either tier into a build, or None if it has gone stale."""
        pinned = self._catalog_ids.get(catalog_id)
        if pinned is not None:
            repo, file = pinned
            size = next(
                (
                    variant.size_bytes
                    for model in self._manifest.models
                    for variant in model.variants
                    if (variant.repo, variant.file) == pinned
                ),
                0,
            )
            return InstallPlan(file.removesuffix(".gguf"), repo, file, size)

        ticket = self._tickets.resolve(catalog_id)
        if ticket is None:
            return None
        return InstallPlan(
            ticket.file.removesuffix(".gguf"), ticket.repo, ticket.file, ticket.size_bytes
        )

    async def install(self, plan: InstallPlan) -> AsyncIterator:
        """Fetch the build into the models directory, under its real filename."""
        url = f"https://huggingface.co/{plan.repo}/resolve/main/{plan.file}"
        async for step in download_gguf(url, self._models_dir / plan.file):
            yield step

    async def wait_until_servable(
        self, model_id: str, *, timeout: float = 30.0, interval: float = 0.5
    ) -> bool:
        """Block until the runtime can actually answer for this model.

        The router learns about a new model only by restarting, which Electron
        triggers when the preset changes, on a poll. Reporting the install
        complete before then tells the user a model is ready while a chat
        returns `model '<id>' not found`, measured as a 400.

        Returns False on timeout rather than raising: the download did succeed,
        the file is on disk, and the model becomes usable once the sidecar comes
        back. A failed install would be the wrong thing to report.
        """
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

    async def search(self, query: str, *, limit: int = 30) -> list[SearchHit]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await search_models(client, query, limit=limit)

    async def repo(self, repo: str) -> dict:
        """Price every build in a repo, exactly, from one header read.

        Architecture fields are identical across quantizations, measured, so one
        read prices the whole ladder and the weights bytes come free from the
        listing.
        """
        budget = self.budget()
        async with httpx.AsyncClient(follow_redirects=True) as client:
            builds = await list_builds(client, repo)
            if not builds:
                return {
                    "repo": repo,
                    "architecture": "",
                    "context_length": 0,
                    "supported": False,
                    "builds": [],
                    "ineligible_reason": "no single file build in this repo",
                }
            url = f"https://huggingface.co/{repo}/resolve/main/{builds[0].file}"
            shape = await shape_from_url(client, url)

        supported = is_supported(shape.architecture)
        rows = []
        for build in builds:
            fit = estimate(shape, build.size_bytes, budget)
            text = badge(fit, budget)
            rows.append(
                {
                    "catalog_id": self._tickets.mint(
                        repo, build.file, build.quantization, build.size_bytes
                    ),
                    "file": build.file,
                    "quantization": build.quantization,
                    "size_bytes": build.size_bytes,
                    "fit": {
                        "state": fit.state.value,
                        "need_bytes": fit.need_bytes,
                        "budget_bytes": fit.budget_bytes,
                        "offload_fraction": fit.offload_fraction,
                        "approximate": False,
                    },
                    "badge": {"verdict": text.verdict, "reason": text.reason},
                    "can_install": fit.can_install and supported,
                }
            )
        return {
            "repo": repo,
            "architecture": shape.architecture,
            "context_length": shape.context_length,
            "supported": supported,
            "builds": rows,
            "ineligible_reason": None
            if supported
            else f"llama.cpp cannot run the {shape.architecture} architecture",
        }

    def devices(self) -> tuple[Device, ...]:
        """Probe once and remember.

        The first call compiles Metal shaders and costs about 19 seconds on a
        Mac; every call after is tens of milliseconds. Warm this in the
        background at launch rather than on the path of the first render.
        """
        if self._devices is None:
            try:
                self._devices = tuple(probe_devices(self._library_dir))
            except OSError:
                # No staged runtime. The catalog still renders, priced against
                # the host, and installs are disabled higher up.
                self._devices = ()
        return self._devices

    def budget(self, mode: BudgetMode = BudgetMode.CAPACITY) -> HardwareBudget:
        """Capacity by default: a catalog is a shelf, not a launch decision.

        Pricing rows against whatever is free this second makes every large row
        read as too big whenever a browser is open.
        """
        return build_budget(self.devices(), available_bytes(), mode=mode)

    def catalog(self) -> Catalog:
        budget = self.budget()
        rows = curated_rows(self._manifest.models, budget)
        pick = recommend(self._manifest.models, budget)
        return Catalog(
            budget=budget,
            devices=self.devices(),
            curated=tuple(rows),
            installed=tuple(self._installed()),
            recommended_model_id=pick.entry.model_id if pick else None,
        )

    def installed(self) -> list[InstalledRow]:
        """What is on disk, which is the only inventory deletion needs."""
        return self._installed()

    def _installed(self) -> list[InstalledRow]:
        """Whatever GGUF files are in the models directory.

        Disk is the source of truth: the router auto-discovers this directory,
        so there is no separate inventory to keep in step with it.
        """
        if not self._models_dir.exists():
            return []
        return sorted(
            (
                InstalledRow(path.stem, path.name, path.stat().st_size)
                for path in self._models_dir.glob("*.gguf")
            ),
            key=lambda row: row.model_id,
        )
