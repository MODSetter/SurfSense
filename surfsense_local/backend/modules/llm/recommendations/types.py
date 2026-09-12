from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FitLevel(StrEnum):
    PERFECT = "perfect"
    GOOD = "good"
    MARGINAL = "marginal"
    TOO_TIGHT = "too_tight"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RecommendationWarning:
    code: str
    message: str


@dataclass(frozen=True)
class SystemProfile:
    cpu_name: str | None = None
    cpu_cores: int | None = None
    total_ram_gb: float | None = None
    available_ram_gb: float | None = None
    has_gpu: bool = False
    gpu_name: str | None = None
    gpu_vram_gb: float | None = None
    gpu_count: int = 0
    backend: str | None = None
    unified_memory: bool = False


@dataclass(frozen=True)
class ScoredModel:
    canonical_id: str
    publisher: str | None
    family: str
    display_name: str
    parameter_count: str | None
    params_b: float | None
    use_case: str | None
    fit: FitLevel
    score: float | None
    runtime: str | None
    run_mode: str | None
    best_quant: str | None
    memory_required_gb: float | None
    memory_available_gb: float | None
    utilization_pct: float | None
    disk_size_gb: float | None
    estimated_tps: float | None
    prefill_tps: float | None
    ttft_ms: float | None
    estimate_confidence: str | None
    estimate_basis: dict[str, Any] | None
    effective_context_length: int | None
    capability_ids: tuple[str, ...]
    license: str | None
    ollama_name: str | None
    gguf_sources: tuple[str, ...]
    notes: tuple[str, ...] = ()
    ollama_quantization: str | None = None


@dataclass(frozen=True)
class AdvisorCatalog:
    system: SystemProfile | None
    models: tuple[ScoredModel, ...]
    llmfit_version: str | None
    warnings: tuple[RecommendationWarning, ...] = ()


@dataclass(frozen=True)
class InstallPlan:
    canonical_id: str
    runtime: str
    model_name: str
    expected_bytes: int | None
    quantization: str | None


@dataclass(frozen=True)
class InstalledModel:
    runtime: str
    model_name: str
    capabilities: tuple[str, ...]
    quantization: str | None = None


@dataclass(frozen=True)
class CatalogRow:
    catalog_id: str
    canonical_id: str
    family: str
    label: str
    publisher: str | None
    parameter_count: str | None
    fit: FitLevel
    score: float | None
    memory_required_gb: float | None
    disk_size_gb: float | None
    estimated_tps: float | None
    prefill_tps: float | None
    ttft_ms: float | None
    effective_context_length: int | None
    estimate_confidence: str | None
    license: str | None
    runtime: str
    runtime_model: str
    quantization: str | None
    installed: bool
    selected: bool
    can_install: bool
    can_delete: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogResult:
    hardware: SystemProfile | None
    llmfit_version: str | None
    recommended: tuple[CatalogRow, ...]
    explore: tuple[CatalogRow, ...]
    installed: tuple[CatalogRow, ...]
    warnings: tuple[RecommendationWarning, ...] = ()
    runtime_status: dict[str, bool] = field(default_factory=dict)
