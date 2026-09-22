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
import threading
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
    list_builds,
    refusal,
    search_models,
)
from modules.llm.catalog.search.eligibility import read_repo_facts
from modules.llm.fit import (
    FitState,
    HardwareBudget,
    ModelShape,
    badge,
    estimate,
    plan_load,
    planned_precision,
)
from modules.llm.gguf.file_kind import FileKind, GgufFile, kind_of
from modules.llm.gguf.shape import to_shape
from modules.llm.gguf.source import header_from_file, header_from_url
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
from modules.llm.providers.llamacpp import (
    PRESET_FILE,
    PROVIDER,
    ModelPreset,
    RouterClient,
    download_gguf,
    projector_for,
    write_presets,
)

logger = logging.getLogger(__name__)

# Priced from the listing alone when a header cannot be read. Every
# architecture-derived term is zero, so `need` is the file size and nothing
# else, and the row is marked approximate so the screen can say so.
# How many builds the candidate walk will read before giving up. A repo
# needs more than a handful of companions sorting ahead of its model for
# this to matter, and each read is a probe, so the cap is about bounding a
# pathological repo rather than a cost anyone pays.
_CANDIDATES = 4

_SIZE_ONLY_SHAPE = ModelShape(
    architecture="",
    block_count=0,
    head_count_kv=0,
    key_length=0,
    value_length=0,
    context_length=0,
    n_vocab=0,
)


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
    # Whether the runtime can reach this machine's graphics hardware. Beside the
    # budget rather than inside it: the budget is memory, this is a diagnosis,
    # and a broken install must not read as a machine that has no card.
    gpu_status: GpuStatus
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
        *,
        probe: Probe = probe_devices,
        os_gpu: OsGpu = os_reports_gpu,
    ) -> None:
        self._runtime_url = runtime_url
        self._manifest = manifest
        self._models_dir = models_dir
        self._library_dir = library_dir
        self._probe = probe
        self._os_gpu = os_gpu
        self._inventory: SystemInventory | None = None
        # The startup warm and the first request race for this.
        self._inventory_lock = threading.Lock()
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
                header = header_from_file(path)
                # A projector is half of a vision model, not a model. It has a
                # header and a size like any other file here, so without this it
                # would be offered as something to chat with. Asked of the file
                # rather than of its name: this loop reads the header anyway, so
                # the name only ever saved a read it was about to do.
                if kind_of(header).kind is not FileKind.MODEL:
                    continue
                shape = to_shape(header)
            except (OSError, ValueError):
                # A truncated or foreign file in the directory. Skipping it
                # costs that one model; failing would leave the runtime dead
                # over a file nobody asked it to load.
                logger.warning("skipping unreadable model %s", path.name)
                continue

            projector = projector_for(path, self._projector_names(path))
            mmproj_bytes = projector.stat().st_size if projector else 0
            plan = plan_load(
                shape, path.stat().st_size, budget, live=live, mmproj_bytes=mmproj_bytes
            )
            presets.append(
                ModelPreset(
                    model_id=path.stem,
                    path=str(path),
                    n_ctx=plan.n_ctx,
                    precision=plan.precision,
                    fit_target_mib=fit_target_mib(mmproj_bytes),
                    mmproj_path=str(projector) if projector else None,
                )
            )
        write_presets(self._models_dir / PRESET_FILE, presets)

    def _projector_names(self, model_path: Path) -> list[str]:
        """What the manifest calls this model's projector, if it is a curated one."""
        return [
            variant.mmproj
            for model in self._manifest.models
            for variant in model.variants
            if variant.mmproj and variant.file == model_path.name
        ]

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
        approximate = False
        chat_template = True
        async with httpx.AsyncClient(follow_redirects=True) as client:
            builds = await list_builds(client, repo)
            if not builds:
                return {
                    "repo": repo,
                    "architecture": "",
                    "context_length": 0,
                    "supported": False,
                    "chat_template": True,
                    "builds": [],
                    "ineligible_reason": "no single file build in this repo",
                }

            # The listing is asked for the pipeline tag and the chat template,
            # which are facts about the repo. It is never asked what the model
            # is: it parses one GGUF per repo and publishes that as the repo's
            # answer, so a chat model shipped beside a vision sidecar comes back
            # as `clip`. Measured, that refused 17 of the 1000 most downloaded
            # repos, 13 of them vision models, each told to install the model it
            # belongs to when the model it belongs to was that repo.
            facts = await read_repo_facts(client, repo)
            tag = facts.pipeline_tag if facts else None
            if facts is not None:
                chat_template = facts.has_chat_template

            candidate, shape = await self._candidate(client, repo, builds)
            if shape is None:
                # The listing is enough to say how large each build is, and a
                # size alone still orders the ladder. Refusing the whole repo
                # over one unreadable header would hide builds the user can run.
                logger.warning("could not read the header for %s", repo)
                shape = _SIZE_ONLY_SHAPE
                approximate = True

        # The file is the authority on what it is; the tag is the authority on
        # what the repo says it is for, and only the tag can catch a model built
        # on a chat architecture and then trained to do something else.
        # A candidate that is not a model means `list_builds` kept a companion,
        # so its architecture says nothing about the repo and only the tag
        # stands. Every path here fails open: the runtime holds the real file
        # and refuses with the same sentence if this was wrong.
        judged = shape.architecture if candidate and candidate.kind is FileKind.MODEL else ""
        reason = refusal(judged, tag)
        if reason:
            return self._ineligible(
                repo,
                builds,
                architecture=judged or (facts.architecture if facts else ""),
                context_length=shape.context_length,
                chat_template=chat_template,
                reason=reason,
            )

        rows = []
        for build in builds:
            # The same precision rule the curated rows and the loader use, so
            # a searched build is described the way it will be loaded.
            fit = estimate(
                shape,
                build.size_bytes,
                budget,
                precision=planned_precision(shape, build.size_bytes, budget),
            )
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
                        "approximate": approximate,
                    },
                    "badge": {"verdict": text.verdict, "reason": text.reason},
                    "can_install": fit.can_install,
                }
            )
        return {
            "repo": repo,
            "architecture": shape.architecture,
            "context_length": shape.context_length,
            "supported": True,
            "chat_template": chat_template,
            "builds": rows,
            "ineligible_reason": None,
        }

    async def _candidate(
        self, client: httpx.AsyncClient, repo: str, builds: list
    ) -> tuple[GgufFile | None, ModelShape | None]:
        """The first build whose own header says it is a model.

        `list_builds` orders by size and a draft head is always smaller than the
        model it accelerates, so in a repo shipping both, the smallest file is a
        companion. Judging it would refuse every build of a working model, which
        is the failure Hugging Face's repo summary used to cause, reproduced
        from our own ordering.

        So the order is a suggestion and the header is the answer. A companion
        costs one probe to rule out, because it carries no tokenizer and its
        metadata ends inside it, while a chat model truncates there and widens
        exactly as it did before.

        The question is "does this repo hold anything runnable", so a build that
        is a model but a denied one keeps the walk going. A draft head declares
        `general.type = model` and is one, structurally; only the denylist knows
        it answers nothing. Refusing on the first denied build would turn away
        a working model shipped beside its own accelerator.

        Stops after `_CANDIDATES` reads, and then reports the last thing it saw
        so the refusal names something real. That is the right answer for a repo
        of nothing but sidecars, which is what a drafter-only repo is.
        """
        last: tuple[GgufFile | None, ModelShape | None] = (None, None)
        for build in builds[:_CANDIDATES]:
            url = f"https://huggingface.co/{repo}/resolve/main/{build.file}"
            try:
                header = await header_from_url(client, url)
            except (httpx.HTTPError, ValueError):
                return last
            found = kind_of(header)
            last = (found, to_shape(header))
            if found.kind is FileKind.MODEL and not refusal(found.architecture):
                return last
        return last

    def _ineligible(
        self,
        repo: str,
        builds: list,
        *,
        architecture: str,
        context_length: int,
        chat_template: bool,
        reason: str,
    ) -> dict:
        """A repo that cannot chat here, described without a further read.

        The reason is passed in rather than recomputed, because two different
        facts produce it and only the caller knows which one fired.

        The builds are still listed, at their real sizes, because the screen is
        answering "what is in here" as well as "can I run it", and an empty repo
        reads as a broken page rather than an unsupported model.
        """
        return {
            "repo": repo,
            "architecture": architecture,
            "context_length": context_length,
            "supported": False,
            "chat_template": chat_template,
            "builds": [
                {
                    "catalog_id": "",
                    "file": build.file,
                    "quantization": build.quantization,
                    "size_bytes": build.size_bytes,
                    "fit": {
                        "state": FitState.TOO_BIG.value,
                        "need_bytes": 0,
                        "budget_bytes": 0,
                        "offload_fraction": 0.0,
                        "approximate": True,
                    },
                    "badge": {"verdict": "Cannot run", "reason": reason},
                    "can_install": False,
                }
                for build in builds
            ],
            "ineligible_reason": reason,
        }

    def inventory(self) -> SystemInventory:
        """Probe once and remember, across every thread that asks.

        The first call compiles Metal shaders and costs about 19 seconds on a
        Mac; every call after is tens of milliseconds. The lock is what makes
        the startup warm worth having: a request arriving during it waits for
        that one probe instead of starting a second.
        """
        with self._inventory_lock:
            if self._inventory is None:
                self._inventory = system_inventory(
                    self._library_dir, probe=self._probe, os_gpu=self._os_gpu
                )
            return self._inventory

    def devices(self) -> tuple[Device, ...]:
        """What ggml can see. Empty is a real answer; `gpu_status` says which."""
        return self.inventory().devices

    def warm(self) -> None:
        """Take the probe and write the preset, off the path of the first render.

        Ordered: the preset is priced against the devices, so probing second
        would mean probing twice.
        """
        self.inventory()
        self.reprice()

    def budget(self, mode: BudgetMode = BudgetMode.CAPACITY) -> HardwareBudget:
        """Capacity by default: a catalog is a shelf, not a launch decision.

        Pricing rows against whatever is free this second makes every large row
        read as too big whenever a browser is open.
        """
        return build_budget(self.devices(), available_bytes(), mode=mode)

    def catalog(self) -> Catalog:
        inventory = self.inventory()
        budget = self.budget()
        rows = curated_rows(self._manifest.models, budget)
        pick = recommend(self._manifest.models, budget)
        return Catalog(
            budget=budget,
            devices=inventory.devices,
            gpu_status=inventory.gpu_status,
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
