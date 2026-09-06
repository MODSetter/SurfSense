from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from modules.llm.models import ModelRole
from modules.llm.recommendations.types import FitLevel


class ProviderRead(BaseModel):
    """A configured provider, and what it can do right now."""

    name: str
    healthy: bool
    can_download: bool
    # BYO-key providers need a key before they answer; the UI shows a key field
    # when one is required and not yet set.
    requires_key: bool
    configured: bool


class ModelRead(BaseModel):
    """A model the provider already has on disk."""

    name: str
    installed: bool
    capabilities: list[str]


class CatalogEntryRead(BaseModel):
    """A model on offer to download, with its size."""

    name: str
    label: str
    size_gb: float
    installed: bool


class PullRequest(BaseModel):
    """The one model to fetch, by its provider name."""

    name: str


class CredentialWrite(BaseModel):
    """The BYO API key a client sets for a provider."""

    api_key: str


class CredentialStatus(BaseModel):
    """Whether a provider has a key on file. The key itself is never returned."""

    provider: str
    configured: bool


class SelectionWrite(BaseModel):
    """The choice a client makes for a role."""

    provider: str
    name: str


class SelectionRead(BaseModel):
    """The model currently answering for a role."""

    model_config = ConfigDict(from_attributes=True)

    role: ModelRole
    provider: str
    name: str
    updated_at: datetime


class RecommendationWarningRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    message: str


class SystemProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cpu_name: str | None
    cpu_cores: int | None
    total_ram_gb: float | None
    available_ram_gb: float | None
    has_gpu: bool
    gpu_name: str | None
    gpu_vram_gb: float | None
    gpu_count: int
    backend: str | None
    unified_memory: bool


class RecommendationSystemRead(BaseModel):
    hardware: SystemProfileRead | None
    llmfit_version: str | None
    estimates_available: bool
    warnings: list[RecommendationWarningRead]


class RecommendationRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    warnings: list[str]


class RecommendationCatalogRead(BaseModel):
    hardware: SystemProfileRead | None
    llmfit_version: str | None
    recommended: list[RecommendationRowRead]
    explore: list[RecommendationRowRead]
    installed: list[RecommendationRowRead]
    warnings: list[RecommendationWarningRead]
    runtime_status: dict[str, bool]


class InstallRequest(BaseModel):
    catalog_id: str = Field(min_length=1, max_length=128)
    select: bool = True
