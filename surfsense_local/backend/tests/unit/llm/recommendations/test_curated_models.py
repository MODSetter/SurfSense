import pytest
from pydantic import ValidationError

from modules.llm.recommendations.curated_models import (
    CuratedModelsManifest,
    load_curated_models,
)

pytestmark = pytest.mark.unit


def _model(**overrides: object) -> dict:
    base = {
        "model_id": "Qwen/Qwen3-8B",
        "family": "Qwen3",
        "minimum_fit": "good",
        "minimum_context": 8192,
        "allowed_quantizations": ["Q4_K_M"],
        "artifacts": {"ollama": {"name": "qwen3:8b", "quantization": "Q4_K_M"}},
        "label": "Qwen3 8B",
        "parameter_count": "8B",
        "size_bytes": 5_225_374_496,
    }
    return {**base, **overrides}


def test_packaged_manifest_has_eight_unique_curated_models() -> None:
    """The policy carries the eight existing Qwen offerings exactly once."""
    manifest = load_curated_models()

    assert manifest.schema_version == 2
    assert manifest.advisor_providers == ["Alibaba"]
    assert len(manifest.models) == 8
    assert len({model.model_id for model in manifest.models}) == 8
    # Every entry has real display metadata, not a placeholder.
    for model in manifest.models:
        assert model.label
        assert model.parameter_count
        assert model.size_bytes > 0


def test_manifest_rejects_duplicate_model_ids() -> None:
    """Ambiguous support policy fails validation instead of silently overriding."""
    model = _model()

    with pytest.raises(ValidationError, match="duplicate model_id"):
        CuratedModelsManifest.model_validate(
            {"schema_version": 2, "models": [model, model]}
        )


def test_manifest_rejects_duplicate_ollama_targets() -> None:
    """Two supported models cannot claim the same runtime artifact."""
    qwen_chat = _model(model_id="Qwen/Qwen3-1.7B")
    qwen_base = _model(model_id="Qwen/Qwen3-1.7B-Base")

    with pytest.raises(ValidationError, match="duplicate runtime target"):
        CuratedModelsManifest.model_validate(
            {"schema_version": 2, "models": [qwen_chat, qwen_base]}
        )


def test_manifest_rejects_missing_display_metadata() -> None:
    """A curated entry without display fields can't render a scan-free row."""
    incomplete = {
        "model_id": "Qwen/Qwen3-8B",
        "family": "Qwen3",
        "minimum_fit": "good",
        "minimum_context": 8192,
        "allowed_quantizations": ["Q4_K_M"],
        "artifacts": {"ollama": {"name": "qwen3:8b", "quantization": "Q4_K_M"}},
    }

    with pytest.raises(ValidationError):
        CuratedModelsManifest.model_validate(
            {"schema_version": 2, "models": [incomplete]}
        )


def test_manifest_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError, match="unsupported curated-model schema"):
        CuratedModelsManifest.model_validate({"schema_version": 1, "models": []})
