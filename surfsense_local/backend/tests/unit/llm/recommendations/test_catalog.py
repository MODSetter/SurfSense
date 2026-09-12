from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.llm.providers.types import DownloadProgress
from modules.llm.recommendations.catalog import (
    CatalogService,
    InsufficientDiskError,
    UnknownCatalogIdError,
)
from modules.llm.recommendations.curated_models import CuratedModelsManifest
from modules.llm.recommendations.types import (
    AdvisorCatalog,
    FitLevel,
    InstalledModel,
    InstallPlan,
    ScoredModel,
    SystemProfile,
)

pytestmark = pytest.mark.unit


def _scored(**changes: object) -> ScoredModel:
    base = ScoredModel(
        canonical_id="Qwen/Qwen3-8B",
        publisher="Qwen",
        family="Qwen",
        display_name="Qwen3-8B",
        parameter_count="8B",
        params_b=8.0,
        use_case="chat",
        fit=FitLevel.GOOD,
        score=80,
        runtime="llamacpp",
        run_mode="gpu",
        best_quant="Q4_K_M",
        memory_required_gb=6,
        memory_available_gb=16,
        utilization_pct=37.5,
        disk_size_gb=5.2,
        estimated_tps=30,
        prefill_tps=None,
        ttft_ms=None,
        estimate_confidence="estimated",
        estimate_basis=None,
        effective_context_length=8192,
        capability_ids=("tool_use",),
        license="apache-2.0",
        ollama_name="qwen3:8b",
        gguf_sources=(),
    )
    return replace(base, **changes)


class Advisor:
    def __init__(self, models: tuple[ScoredModel, ...]) -> None:
        self.models = models
        self.calls = 0

    async def scan(self, max_context: int) -> AdvisorCatalog:
        self.calls += 1
        return AdvisorCatalog(
            SystemProfile(available_ram_gb=16),
            self.models,
            "1.1.11",
        )


class Runtime:
    name = "ollama"

    def __init__(self, installed: list[InstalledModel] | None = None) -> None:
        self._installed = installed or []

    async def health(self) -> bool:
        return True

    async def resolve(self, model: ScoredModel) -> InstallPlan | None:
        if not model.ollama_name:
            return None
        return InstallPlan(
            model.canonical_id,
            self.name,
            model.ollama_name,
            100,
            model.ollama_quantization or model.best_quant,
        )

    async def installed_models(self) -> list[InstalledModel]:
        return self._installed

    async def install(self, plan: InstallPlan):
        yield DownloadProgress("success")


class LlamaRuntime(Runtime):
    name = "llamacpp"

    async def resolve(self, model: ScoredModel) -> InstallPlan | None:
        if not model.gguf_sources:
            return None
        return InstallPlan(
            model.canonical_id,
            self.name,
            model.gguf_sources[0],
            100,
            model.best_quant,
        )


def _manifest() -> CuratedModelsManifest:
    return CuratedModelsManifest.model_validate(
        {
            "schema_version": 1,
            "models": [
                {
                    "model_id": "Qwen/Qwen3-8B",
                    "family": "Qwen3",
                    "minimum_fit": "good",
                    "minimum_context": 8192,
                    "allowed_quantizations": ["Q4_K_M"],
                    "artifacts": {
                        "ollama": {
                            "name": "qwen3:8b",
                            "quantization": "Q4_K_M",
                        }
                    },
                }
            ],
        }
    )


def _qwen_1_7_manifest() -> CuratedModelsManifest:
    return CuratedModelsManifest.model_validate(
        {
            "schema_version": 1,
            "models": [
                {
                    "model_id": "Qwen/Qwen3-1.7B",
                    "family": "Qwen3",
                    "minimum_fit": "good",
                    "minimum_context": 8192,
                    "allowed_quantizations": ["Q4_K_M"],
                    "artifacts": {
                        "ollama": {
                            "name": "qwen3:1.7b",
                            "quantization": "Q4_K_M",
                        }
                    },
                }
            ],
        }
    )


async def test_catalog_partitions_recommended_explore_and_embeddings() -> None:
    """Only exact policy matches become recommended; embeddings stay excluded."""
    other = _scored(
        canonical_id="Other/Chat-3B",
        display_name="Chat-3B",
        ollama_name="other:3b",
    )
    embedding = _scored(
        canonical_id="BAAI/bge",
        use_case="embedding",
        capability_ids=("embedding",),
        ollama_name="bge",
    )
    service = CatalogService(
        Advisor((other, embedding, _scored(best_quant="mlx-4bit"))),
        [Runtime()],
        _manifest(),
        max_context=8192,
        reserve_gb=2,
    )

    result = await service.catalog(selected=None)

    assert [row.canonical_id for row in result.recommended] == ["Qwen/Qwen3-8B"]
    assert [row.canonical_id for row in result.explore] == ["Other/Chat-3B"]
    assert result.recommended[0].family == "Qwen3"
    assert result.recommended[0].quantization == "Q4_K_M"


async def test_memory_reserve_can_only_downgrade_fit() -> None:
    """SurfSense peak memory turns a nominal good fit into a warning."""
    service = CatalogService(
        Advisor((_scored(memory_required_gb=13.0),)),
        [Runtime()],
        _manifest(),
        max_context=8192,
        reserve_gb=2,
    )

    result = await service.catalog(selected=None)

    assert result.recommended == ()
    assert result.explore[0].fit is FitLevel.MARGINAL


async def test_installed_models_are_authoritative_and_not_duplicated() -> None:
    """Runtime inventory wins over llmfit's installed metadata."""
    runtime = Runtime([InstalledModel("ollama", "qwen3:8b", ("completion",), "Q4_K_M")])
    service = CatalogService(
        Advisor((_scored(),)),
        [runtime],
        _manifest(),
        max_context=8192,
        reserve_gb=2,
    )

    result = await service.catalog(selected=("ollama", "qwen3:8b"))

    assert result.recommended == ()
    assert len(result.installed) == 1
    assert result.installed[0].selected is True
    assert result.installed[0].can_delete is True


async def test_embedding_only_installed_models_stay_out_of_generation_catalog() -> None:
    """An external Ollama embedding model is not a chat model."""
    runtime = Runtime(
        [InstalledModel("ollama", "nomic-embed-text", ("embedding",), "F16")]
    )
    service = CatalogService(
        Advisor(()),
        [runtime],
        _manifest(),
        max_context=8192,
        reserve_gb=2,
    )

    result = await service.catalog(selected=None)

    assert result.installed == ()


@pytest.mark.parametrize("curated_first", [False, True])
async def test_curated_model_owns_a_colliding_runtime_target(
    curated_first: bool,
) -> None:
    """The explicit Qwen policy wins regardless of llmfit result order."""
    qwen_base = _scored(
        canonical_id="Qwen/Qwen3-1.7B-Base",
        display_name="Qwen3-1.7B-Base",
        score=72.8,
        ollama_name="qwen3:1.7b",
    )
    qwen_chat = _scored(
        canonical_id="Qwen/Qwen3-1.7B",
        display_name="Qwen3-1.7B",
        score=69.2,
        ollama_name=None,
    )
    models = (qwen_chat, qwen_base) if curated_first else (qwen_base, qwen_chat)
    runtime = Runtime(
        [InstalledModel("ollama", "qwen3:1.7b", ("completion",), "Q4_K_M")]
    )
    service = CatalogService(
        Advisor(models),
        [runtime],
        _qwen_1_7_manifest(),
        max_context=8192,
        reserve_gb=2,
    )

    result = await service.catalog(selected=("ollama", "qwen3:1.7b"))

    assert result.recommended == ()
    assert result.explore == ()
    assert [row.canonical_id for row in result.installed] == ["Qwen/Qwen3-1.7B"]
    assert result.installed[0].selected is True
    assert not any(
        warning.code == "ambiguous_runtime_target" for warning in result.warnings
    )


async def test_ambiguous_non_curated_models_use_exact_runtime_target(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Conflicting names become one exact runtime-target row."""
    instruct = _scored(
        canonical_id="meta-llama/Llama-3.2-1B-Instruct",
        display_name="Llama-3.2-1B-Instruct",
        ollama_name="llama3.2:1b",
    )
    base = _scored(
        canonical_id="meta-llama/Llama-3.2-1B",
        display_name="Llama-3.2-1B",
        ollama_name="llama3.2:1b",
    )
    service = CatalogService(
        Advisor((instruct, base)),
        [Runtime()],
        CuratedModelsManifest(schema_version=1, models=[]),
        max_context=8192,
        reserve_gb=2,
    )

    with caplog.at_level("WARNING"):
        result = await service.catalog(selected=None)
        repeated = await service.catalog(selected=None)

    assert result.recommended == ()
    assert len(result.explore) == 1
    assert result.explore[0].canonical_id == "ollama:llama3.2:1b"
    assert result.explore[0].label == "llama3.2:1b"
    assert result.explore[0].runtime_model == "llama3.2:1b"
    assert result.installed == ()
    assert result.warnings == ()
    assert repeated.warnings == ()
    _, resolved_model, plan = await service.preflight(result.explore[0].catalog_id)
    assert resolved_model.canonical_id == "ollama:llama3.2:1b"
    assert plan.model_name == "llama3.2:1b"
    assert (
        caplog.messages.count(
            "Representing ambiguous models meta-llama/Llama-3.2-1B, "
            "meta-llama/Llama-3.2-1B-Instruct as runtime target "
            "ollama:llama3.2:1b"
        )
        == 1
    )


async def test_refresh_invalidates_opaque_install_ids() -> None:
    """A catalog id cannot select an artifact after its scan generation changes."""
    advisor = Advisor((_scored(),))
    service = CatalogService(
        advisor,
        [Runtime()],
        _manifest(),
        max_context=8192,
        reserve_gb=2,
    )
    first = await service.catalog(selected=None)
    old_id = first.recommended[0].catalog_id

    await service.catalog(selected=None, refresh=True)

    with pytest.raises(UnknownCatalogIdError):
        await service.preflight(old_id)
    assert advisor.calls == 2


async def test_a_second_runtime_needs_no_advisor_or_schema_change() -> None:
    """A future GGUF runtime plugs into resolution without changing catalog DTOs."""
    model = _scored(ollama_name=None, gguf_sources=("org/model-q4.gguf",))
    service = CatalogService(
        Advisor((model,)),
        [Runtime(), LlamaRuntime()],
        CuratedModelsManifest(schema_version=1, models=[]),
        max_context=8192,
        reserve_gb=2,
    )

    result = await service.catalog(selected=None)

    assert result.explore[0].runtime == "llamacpp"
    assert result.explore[0].runtime_model == "org/model-q4.gguf"


async def test_disk_space_is_rejected_before_install_streaming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Managed runtime storage is checked before response headers are sent."""
    service = CatalogService(
        Advisor((_scored(),)),
        [Runtime()],
        _manifest(),
        max_context=8192,
        reserve_gb=2,
        runtime_storage={"ollama": tmp_path},
    )
    catalog = await service.catalog(selected=None)
    monkeypatch.setattr(
        "modules.llm.recommendations.catalog.shutil.disk_usage",
        lambda _path: SimpleNamespace(free=50),
    )

    with pytest.raises(InsufficientDiskError):
        await service.preflight(catalog.recommended[0].catalog_id)
