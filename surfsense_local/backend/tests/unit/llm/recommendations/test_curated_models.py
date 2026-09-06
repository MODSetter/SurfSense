import pytest
from pydantic import ValidationError

from modules.llm.recommendations.curated_models import (
    CuratedModelsManifest,
    load_curated_models,
)

pytestmark = pytest.mark.unit


def test_packaged_manifest_has_eight_unique_curated_models() -> None:
    """The v1 policy migrates the eight existing Qwen offerings exactly once."""
    manifest = load_curated_models()

    assert manifest.schema_version == 1
    assert manifest.advisor_providers == ["Alibaba"]
    assert len(manifest.models) == 8
    assert len({model.model_id for model in manifest.models}) == 8


def test_manifest_rejects_duplicate_model_ids() -> None:
    """Ambiguous support policy fails validation instead of silently overriding."""
    model = {
        "model_id": "Qwen/Qwen3-8B",
        "family": "Qwen3",
        "minimum_fit": "good",
        "minimum_context": 8192,
        "allowed_quantizations": ["Q4_K_M"],
        "artifacts": {"ollama": {"name": "qwen3:8b", "quantization": "Q4_K_M"}},
    }

    with pytest.raises(ValidationError, match="duplicate model_id"):
        CuratedModelsManifest.model_validate(
            {"schema_version": 1, "models": [model, model]}
        )
