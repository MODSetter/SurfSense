"""llama.cpp behind the engine seam: chat models in llama-server's folder."""

import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

import httpx

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.engines.engine import InstallStep
from modules.llm.catalog.local.engines.llamacpp import ENGINE
from modules.llm.catalog.local.engines.llamacpp.models_folder.preset import (
    preset_model_ids,
    write_preset,
)
from modules.llm.catalog.local.engines.llamacpp.models_folder.readiness import (
    become_ready,
)
from modules.llm.catalog.local.engines.llamacpp.models_folder.scan import (
    DownloadedModel,
    ProjectorNotice,
    projector_notices,
    scan,
)
from modules.llm.catalog.local.engines.llamacpp.pricing import price
from modules.llm.catalog.local.engines.llamacpp.rows.catalog import local_catalog
from modules.llm.catalog.local.engines.llamacpp.search.exact_check import check_build
from modules.llm.catalog.local.engines.llamacpp.search.hits import (
    SearchHit,
    search_models,
)
from modules.llm.catalog.local.engines.llamacpp.search.listing import read_listing
from modules.llm.catalog.local.engines.llamacpp.search.repo_row import repo_row
from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.installs import projector_filename, read_installs
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.fit import FitState, HardwareBudget
from modules.llm.hardware import BudgetMode
from modules.llm.model_type import ModelType
from modules.llm.providers.llamacpp import PROVIDER
from modules.llm.providers.llamacpp.router_client import RouterClient

_TOO_BIG = "This build is too big for this computer. Pick a smaller one."


# An unload is quick. The client's own read timeout is sized for a load.
UNLOAD_WAIT_SECONDS = 10.0

class LlamaCppEngine:
    name = ENGINE
    model_types = (ModelType.TEXT_GEN,)
    provider = PROVIDER
    server_follows_selection = False

    def __init__(
        self,
        models_dir: Path,
        runtime_url: str,
        budget: Callable[[BudgetMode], HardwareBudget],
    ) -> None:
        self._models_dir = models_dir
        self._runtime_url = runtime_url
        self._budget = budget
        self._preset_lock = threading.Lock()

    @property
    def folder(self) -> Path:
        return self._models_dir

    def installed(self) -> list[DownloadedModel]:
        """The models on disk, read from their own headers."""
        return scan(self._models_dir, read_installs(self._models_dir))

    def projector_notices(self) -> tuple[ProjectorNotice, ...]:
        """Unpaired projectors and the model they identify, when exactly one."""
        return projector_notices(self._models_dir, self.installed())

    def rows(
        self,
        models: Sequence[CuratedModel],
        mint: Callable[[Build], str],
        *,
        selected: str | None,
    ) -> tuple[LocalRow, ...]:
        installed = self.installed()
        self._reprice_for_copied_models(installed)
        return local_catalog(
            models,
            installed,
            self._budget(BudgetMode.CAPACITY),
            mint,
            selected=selected,
        ).rows

    def landing(self, file: BuildFile, model_id: str) -> str:
        """A projector takes the model's name, so two vision models never share
        or overwrite one."""
        if file.role is FileRole.PROJECTOR:
            return projector_filename(model_id)
        return file.name

    def holds(self, model_id: str) -> bool:
        return any(m.model_id == model_id for m in self.installed())

    def bundled(self, model_id: str) -> bool:
        return False  # every chat model is a download

    def reprice(self) -> None:
        """Rewrite the preset for everything on disk."""
        installed = self.installed()
        with self._preset_lock:
            self._write_preset(installed)

    def _reprice_for_copied_models(self, installed: Sequence[DownloadedModel]) -> None:
        model_ids = frozenset(
            model.model_id for model in installed if model.shape is not None
        )
        with self._preset_lock:
            if not model_ids <= preset_model_ids(self._models_dir):
                self._write_preset(installed)

    def _write_preset(self, installed: Sequence[DownloadedModel]) -> None:
        write_preset(
            self._models_dir,
            installed,
            self._budget(BudgetMode.CAPACITY),
            self._budget(BudgetMode.LIVE),
        )

    async def check(self, plan: InstallPlan) -> InstallPlan:
        """Refuse what cannot run here, before any bytes move: a curated build by
        its committed shape, a searched one by reading its headers. Returns the
        plan with a failed projector dropped."""
        if not plan.needs_check:
            self._refuse_curated_too_big(plan)
            return plan
        async with httpx.AsyncClient(follow_redirects=True) as client:
            checked = await check_build(
                client, plan.build, plan.pipeline_tag, self._budget(BudgetMode.CAPACITY)
            )
        if not checked.is_model:
            raise InstallRefusedError(
                "This file is not a model SurfSense can run.", InstallCode.NOT_A_MODEL
            )
        if ModelType.TEXT_GEN not in checked.classification.types:
            raise InstallRefusedError(
                checked.classification.reason or "SurfSense cannot run this model."
            )
        if checked.fit.state is FitState.TOO_BIG:
            raise InstallRefusedError(_TOO_BIG, InstallCode.TOO_BIG)
        return InstallPlan(
            plan.model_id, checked.build, self.name, pipeline_tag=plan.pipeline_tag
        )

    def _refuse_curated_too_big(self, plan: InstallPlan) -> None:
        # A curated build's header was read at refresh time; whether it fits
        # this machine was not. Priced as its row is, and only TOO_BIG
        # refuses: a build that spills runs, slower, and stays the user's
        # to choose.
        projector = plan.build.projector
        fit = price(
            plan.shape,
            plan.build.weights_bytes,
            projector.size_bytes if projector else 0,
            self._budget(BudgetMode.CAPACITY),
        )
        if fit.state is FitState.TOO_BIG:
            raise InstallRefusedError(_TOO_BIG, InstallCode.TOO_BIG)

    async def after_install(self, model_id: str) -> AsyncIterator[InstallStep]:
        # The router only learns about a model by restarting, and reporting
        # complete before then promises a model a chat cannot reach.
        self.reprice()
        async for step in become_ready(self._runtime_url, model_id):
            yield step

    def after_remove(self) -> None:
        # A stale section is served as a real entry and fails when chosen.
        self.reprice()

    async def release(self, model_id: str) -> None:
        # The router never unloads on its own, and an unchanged preset is not
        # rewritten, so nothing restarts it either.
        # Refused when not loaded or no router: no worker of ours has the file.
        # A silent router has nothing to wait for either: the caller holds the
        # install lock.
        with contextlib.suppress(httpx.HTTPError, TimeoutError):
            async with asyncio.timeout(UNLOAD_WAIT_SECONDS):
                await RouterClient(self._runtime_url).unload(model_id)

    def on_startup(self) -> None:
        self.reprice()

    async def search(self, query: str, *, limit: int = 30) -> list[SearchHit]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await search_models(client, query, limit=limit)

    async def repo(
        self, repo: str, mint: Callable[[Build, str | None], str]
    ) -> tuple[LocalRow, bool]:
        """One repo's builds from its listing, and whether it needs an account."""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            listing = await read_listing(client, repo)
        row = repo_row(
            listing,
            self._budget(BudgetMode.CAPACITY),
            lambda build: mint(build, listing.pipeline_tag),
        )
        return row, listing.gated
