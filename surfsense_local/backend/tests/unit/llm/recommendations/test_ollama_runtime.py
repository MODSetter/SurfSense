from dataclasses import replace

import pytest

from modules.llm.providers.ollama.provider import OllamaProvider
from modules.llm.recommendations.types import FitLevel, ScoredModel

pytestmark = pytest.mark.unit


def _model(ollama_name: str | None = "qwen3:8b") -> ScoredModel:
    return ScoredModel(
        canonical_id="Qwen/Qwen3-8B",
        publisher="Qwen",
        family="Qwen3",
        display_name="Qwen3-8B",
        parameter_count="8B",
        params_b=8,
        use_case="chat",
        fit=FitLevel.GOOD,
        score=80,
        runtime="llamacpp",
        run_mode="gpu",
        best_quant="Q4_K_M",
        memory_required_gb=6,
        memory_available_gb=16,
        utilization_pct=40,
        disk_size_gb=5.2,
        estimated_tps=30,
        prefill_tps=None,
        ttft_ms=None,
        estimate_confidence="estimated",
        estimate_basis=None,
        effective_context_length=8192,
        capability_ids=("tool_use",),
        license="apache-2.0",
        ollama_name=ollama_name,
        gguf_sources=(),
    )


async def test_ollama_resolves_only_advisor_mappings() -> None:
    """The renderer cannot invent the tag placed in an install plan."""
    runtime = OllamaProvider("http://127.0.0.1:1")

    assert await runtime.resolve(_model(None)) is None
    plan = await runtime.resolve(
        replace(
            _model(),
            best_quant="mlx-4bit",
            ollama_quantization="Q4_K_M",
        )
    )

    assert plan is not None
    assert plan.model_name == "qwen3:8b"
    assert plan.quantization == "Q4_K_M"
    assert plan.expected_bytes == 5_200_000_000


async def test_ollama_rejects_another_runtimes_plan() -> None:
    """A trusted plan remains bound to the runtime that resolved it."""
    runtime = OllamaProvider("http://127.0.0.1:1")
    plan = await runtime.resolve(_model())
    assert plan is not None

    with pytest.raises(ValueError):
        runtime.install(replace(plan, runtime="llamacpp"))
