"""llama.cpp behind the engine seam: chat models in llama-server's folder."""

from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

import httpx

from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.engine import InstallStep
from modules.llm.catalog.local.engines.llamacpp import ENGINE
from modules.llm.catalog.local.engines.llamacpp.models_folder.preset import write_preset
from modules.llm.catalog.local.engines.llamacpp.models_folder.readiness import (
    become_ready,
)
from modules.llm.catalog.local.engines.llamacpp.models_folder.scan import (
    DownloadedModel,
    scan,
)
from modules.llm.catalog.local.engines.llamacpp.rows.catalog import local_catalog
from modules.llm.catalog.local.engines.llamacpp.search.exact_check import check_build
from modules.llm.catalog.local.engines.llamacpp.search.hits import (
    SearchHit,
    search_models,
)
from modules.llm.catalog.local.engines.llamacpp.search.listing import read_listing
from modules.llm.catalog.local.engines.llamacpp.search.repo_row import repo_row
from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.installs import read_installs
from modules.llm.catalog.local.manifest import CuratedModel
from modules.llm.catalog.local.rows import LocalRow
from modules.llm.fit import FitState, HardwareBudget
from modules.llm.hardware import BudgetMode
from modules.llm.model_type import ModelType
from modules.llm.providers.llamacpp import PROVIDER


class LlamaCppEngine:
    name = ENGINE
    model_type = ModelType.TEXT_GEN
    provider = PROVIDER

    def __init__(
        self,
        models_dir: Path,
        runtime_url: str,
        budget: Callable[[BudgetMode], HardwareBudget],
    ) -> None:
        self._models_dir = models_dir
        self._runtime_url = runtime_url
        self._budget = budget

    @property
    def folder(self) -> Path:
        return self._models_dir

    def installed(self) -> list[DownloadedModel]:
        """The models on disk, read from their own headers."""
        return scan(self._models_dir, read_installs(self._models_dir))

    def rows(
        self,
        models: Sequence[CuratedModel],
        mint: Callable[[Build], str],
        *,
        selected: str | None,
    ) -> tuple[LocalRow, ...]:
        return local_catalog(
            models,
            self.installed(),
            self._budget(BudgetMode.CAPACITY),
            mint,
            selected=selected,
        ).rows

    def holds(self, model_id: str) -> bool:
        return any(m.model_id == model_id for m in self.installed())

    def reprice(self) -> None:
        """Rewrite the preset for everything on disk."""
        write_preset(
            self._models_dir,
            self.installed(),
            self._budget(BudgetMode.CAPACITY),
            self._budget(BudgetMode.LIVE),
        )

    async def check(self, plan: InstallPlan) -> InstallPlan:
        """Read a searched build's headers and refuse what cannot run, before any
        bytes move. Returns the plan with a failed projector dropped."""
        if not plan.needs_check:
            return plan
        async with httpx.AsyncClient(follow_redirects=True) as client:
            checked = await check_build(
                client, plan.build, plan.pipeline_tag, self._budget(BudgetMode.CAPACITY)
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
        return InstallPlan(
            plan.model_id, checked.build, self.name, pipeline_tag=plan.pipeline_tag
        )

    async def after_install(self, model_id: str) -> AsyncIterator[InstallStep]:
        # The router only learns about a model by restarting, and reporting
        # complete before then promises a model a chat cannot reach.
        self.reprice()
        async for step in become_ready(self._runtime_url, model_id):
            yield step

    def after_remove(self) -> None:
        # A stale section is served as a real entry and fails when chosen.
        self.reprice()

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
