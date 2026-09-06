import asyncio
import secrets
import shutil
from dataclasses import replace
from pathlib import Path

from modules.llm.recommendations.curated_models import (
    CuratedModel,
    CuratedModelsManifest,
)
from modules.llm.recommendations.protocols import LocalRuntime, ModelAdvisor
from modules.llm.recommendations.types import (
    AdvisorCatalog,
    CatalogResult,
    CatalogRow,
    FitLevel,
    InstalledModel,
    InstallPlan,
    RecommendationWarning,
    ScoredModel,
)

FIT_ORDER = {
    FitLevel.PERFECT: 0,
    FitLevel.GOOD: 1,
    FitLevel.MARGINAL: 2,
    FitLevel.TOO_TIGHT: 3,
    FitLevel.UNKNOWN: 4,
}


class UnknownCatalogIdError(ValueError):
    pass


class RuntimeBusyError(RuntimeError):
    pass


class InsufficientDiskError(RuntimeError):
    def __init__(self, required: int, available: int) -> None:
        super().__init__("insufficient disk space")
        self.required = required
        self.available = available


class CatalogService:
    def __init__(
        self,
        advisor: ModelAdvisor,
        runtimes: list[LocalRuntime],
        curated_models: CuratedModelsManifest,
        *,
        max_context: int,
        reserve_gb: float,
        runtime_storage: dict[str, Path] | None = None,
        initial_warnings: tuple[RecommendationWarning, ...] = (),
    ) -> None:
        self._advisor = advisor
        self._runtimes = {runtime.name: runtime for runtime in runtimes}
        self._curated_models = {
            model.model_id: model for model in curated_models.models
        }
        self._max_context = max_context
        self._reserve_gb = reserve_gb
        self._runtime_storage = runtime_storage or {}
        self._initial_warnings = initial_warnings
        self._scan: AdvisorCatalog | None = None
        self._scan_lock = asyncio.Lock()
        self._ids: dict[tuple[str, str], str] = {}
        self._plans: dict[str, tuple[LocalRuntime, ScoredModel, InstallPlan]] = {}
        self._install_locks = {runtime.name: asyncio.Lock() for runtime in runtimes}

    async def advisor_catalog(self, *, refresh: bool = False) -> AdvisorCatalog:
        async with self._scan_lock:
            if refresh:
                self._scan = None
                self._ids.clear()
                self._plans.clear()
            if self._scan is None:
                self._scan = await self._advisor.scan(self._max_context)
            return self._scan

    async def catalog(
        self,
        *,
        selected: tuple[str, str] | None,
        refresh: bool = False,
    ) -> CatalogResult:
        scan = await self.advisor_catalog(refresh=refresh)
        health_results = await asyncio.gather(
            *(runtime.health() for runtime in self._runtimes.values()),
            return_exceptions=True,
        )
        runtime_status = dict(
            zip(
                self._runtimes,
                (
                    result if isinstance(result, bool) else False
                    for result in health_results
                ),
                strict=True,
            )
        )
        inventories = await asyncio.gather(
            *(runtime.installed_models() for runtime in self._runtimes.values()),
            return_exceptions=True,
        )
        installed_by_key: dict[tuple[str, str], InstalledModel] = {}
        warnings = [*self._initial_warnings, *scan.warnings]
        warnings.extend(
            RecommendationWarning(
                "runtime_health_failed",
                f"Could not check {name}.",
            )
            for name, result in zip(self._runtimes, health_results, strict=True)
            if isinstance(result, BaseException)
        )
        for (runtime_name, _runtime), inventory in zip(
            self._runtimes.items(), inventories, strict=True
        ):
            if isinstance(inventory, BaseException):
                warnings.append(
                    RecommendationWarning(
                        "runtime_inventory_failed",
                        f"Could not read installed models from {runtime_name}.",
                    )
                )
                continue
            installed_by_key.update(
                {(model.runtime, model.model_name): model for model in inventory}
            )

        recommended: list[CatalogRow] = []
        explore: list[CatalogRow] = []
        installed: list[CatalogRow] = []
        matched_installed: set[tuple[str, str]] = set()
        self._plans.clear()

        for raw_model in scan.models:
            if _is_embedding(raw_model):
                continue
            model, curated_model = self._apply_curated_model(raw_model)
            model = _apply_reserve(model, self._reserve_gb)
            resolved = await self._resolve(model)
            if resolved is None:
                continue
            runtime, plan = resolved
            key = (runtime.name, plan.model_name)
            is_installed = key in installed_by_key
            row = self._row(
                model,
                plan,
                installed=is_installed,
                selected=selected == key,
                can_install=runtime_status.get(runtime.name, False),
            )
            self._plans[row.catalog_id] = (runtime, model, plan)
            if is_installed:
                installed.append(row)
                matched_installed.add(key)
            elif _is_recommended(model, curated_model):
                recommended.append(row)
            elif model.fit in {
                FitLevel.PERFECT,
                FitLevel.GOOD,
                FitLevel.MARGINAL,
            }:
                explore.append(row)

        for key, local_model in installed_by_key.items():
            if key in matched_installed:
                continue
            catalog_id = self._id(f"{key[0]}:{key[1]}", key[0])
            installed.append(
                CatalogRow(
                    catalog_id=catalog_id,
                    canonical_id=f"{key[0]}:{key[1]}",
                    family=key[1].split(":", 1)[0],
                    label=key[1],
                    publisher=None,
                    parameter_count=None,
                    fit=FitLevel.UNKNOWN,
                    score=None,
                    memory_required_gb=None,
                    disk_size_gb=None,
                    estimated_tps=None,
                    prefill_tps=None,
                    ttft_ms=None,
                    effective_context_length=None,
                    estimate_confidence=None,
                    license=None,
                    runtime=key[0],
                    runtime_model=key[1],
                    quantization=local_model.quantization,
                    installed=True,
                    selected=selected == key,
                    can_install=False,
                    warnings=("No current llmfit estimate is available.",),
                )
            )

        return CatalogResult(
            hardware=scan.system,
            llmfit_version=scan.llmfit_version,
            recommended=tuple(sorted(recommended, key=_sort_key)),
            explore=tuple(sorted(explore, key=_sort_key)),
            installed=tuple(sorted(installed, key=_sort_key)),
            warnings=tuple(warnings),
            runtime_status=runtime_status,
        )

    async def preflight(
        self, catalog_id: str
    ) -> tuple[LocalRuntime, ScoredModel, InstallPlan]:
        found = self._plans.get(catalog_id)
        if found is None:
            raise UnknownCatalogIdError(catalog_id)
        runtime, model, old_plan = found
        plan = await runtime.resolve(model)
        if plan is None or plan != old_plan:
            raise UnknownCatalogIdError(catalog_id)
        if not await runtime.health():
            raise RuntimeError(f"{runtime.name} is unavailable")
        storage = self._runtime_storage.get(runtime.name)
        if storage is not None and plan.expected_bytes is not None:
            available = shutil.disk_usage(storage).free
            if available < plan.expected_bytes:
                raise InsufficientDiskError(plan.expected_bytes, available)
        return runtime, model, plan

    def install_lock(self, runtime: str) -> asyncio.Lock:
        return self._install_locks[runtime]

    def _apply_curated_model(
        self, model: ScoredModel
    ) -> tuple[ScoredModel, CuratedModel | None]:
        curated_model = self._curated_models.get(model.canonical_id)
        if curated_model is None:
            return model, None
        ollama = curated_model.artifacts.ollama
        return (
            replace(
                model,
                family=curated_model.family,
                ollama_name=ollama.name if ollama is not None else model.ollama_name,
                ollama_quantization=(
                    ollama.quantization if ollama is not None else None
                ),
            ),
            curated_model,
        )

    async def _resolve(
        self, model: ScoredModel
    ) -> tuple[LocalRuntime, InstallPlan] | None:
        for runtime in self._runtimes.values():
            plan = await runtime.resolve(model)
            if plan is not None:
                return runtime, plan
        return None

    def _row(
        self,
        model: ScoredModel,
        plan: InstallPlan,
        *,
        installed: bool,
        selected: bool,
        can_install: bool,
    ) -> CatalogRow:
        warnings = list(model.notes)
        if model.fit is FitLevel.MARGINAL:
            warnings.append("This model may be slow or fail at long context.")
        if model.fit is FitLevel.TOO_TIGHT:
            warnings.append("This model is too large for the available memory.")
        return CatalogRow(
            catalog_id=self._id(model.canonical_id, plan.runtime),
            canonical_id=model.canonical_id,
            family=model.family,
            label=model.display_name,
            publisher=model.publisher,
            parameter_count=model.parameter_count,
            fit=model.fit,
            score=model.score,
            memory_required_gb=model.memory_required_gb,
            disk_size_gb=model.disk_size_gb,
            estimated_tps=model.estimated_tps,
            prefill_tps=model.prefill_tps,
            ttft_ms=model.ttft_ms,
            effective_context_length=model.effective_context_length,
            estimate_confidence=model.estimate_confidence,
            license=model.license,
            runtime=plan.runtime,
            runtime_model=plan.model_name,
            quantization=plan.quantization,
            installed=installed,
            selected=selected,
            can_install=can_install and model.fit is not FitLevel.TOO_TIGHT,
            warnings=tuple(warnings),
        )

    def _id(self, canonical_id: str, runtime: str) -> str:
        key = (canonical_id, runtime)
        if key not in self._ids:
            self._ids[key] = secrets.token_urlsafe(18)
        return self._ids[key]


def _is_embedding(model: ScoredModel) -> bool:
    return (model.use_case is not None and "embedding" in model.use_case) or (
        bool(model.capability_ids)
        and set(model.capability_ids).issubset({"embedding", "embeddings"})
    )


def _apply_reserve(model: ScoredModel, reserve_gb: float) -> ScoredModel:
    required = model.memory_required_gb
    available = model.memory_available_gb
    if required is None or available is None:
        return model
    adjusted = max(0.0, available - reserve_gb)
    utilization = required / adjusted if adjusted else float("inf")
    fit = model.fit
    if utilization > 1:
        fit = FitLevel.TOO_TIGHT
    elif utilization > 0.9 and FIT_ORDER[fit] < FIT_ORDER[FitLevel.MARGINAL]:
        fit = FitLevel.MARGINAL
    return replace(model, fit=fit, utilization_pct=utilization * 100)


def _is_recommended(model: ScoredModel, curated_model: CuratedModel | None) -> bool:
    return (
        curated_model is not None
        and model.fit in {FitLevel.PERFECT, FitLevel.GOOD}
        and (model.effective_context_length or 0) >= curated_model.minimum_context
        and (
            not curated_model.allowed_quantizations
            or model.ollama_quantization in curated_model.allowed_quantizations
        )
    )


def _sort_key(row: CatalogRow) -> tuple[int, float, str]:
    return (FIT_ORDER[row.fit], -(row.score or 0), row.canonical_id)
