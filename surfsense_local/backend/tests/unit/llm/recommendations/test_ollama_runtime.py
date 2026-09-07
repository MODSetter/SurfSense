import json
from dataclasses import replace
from pathlib import Path

import pytest

from modules.llm.providers.ollama.provider import OllamaProvider
from modules.llm.recommendations.types import FitLevel, ScoredModel
from shared.config import get_llm_settings

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


async def test_cancel_cleanup_removes_only_partial_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancelling reclaims partial and orphan files without deleting shared blobs."""
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    manifests = tmp_path / "manifests" / "registry.ollama.ai" / "library" / "qwen"
    manifests.mkdir(parents=True)
    referenced = blobs / "sha256-referenced"
    orphan = blobs / "sha256-orphan"
    partials = [
        blobs / "sha256-first-partial",
        blobs / "sha256-first-partial-0",
        blobs / "sha256-second.tmp",
    ]
    referenced.write_bytes(b"keep")
    orphan.write_bytes(b"discard")
    for partial in partials:
        partial.write_bytes(b"discard")
    (manifests / "latest").write_text(
        json.dumps(
            {
                "config": {"digest": "sha256:referenced"},
                "layers": [],
            }
        )
    )
    monkeypatch.setattr(get_llm_settings(), "ollama_models_dir", tmp_path)

    await OllamaProvider("http://127.0.0.1:1").cleanup_cancelled_download()

    assert referenced.exists()
    assert not orphan.exists()
    assert not any(partial.exists() for partial in partials)
