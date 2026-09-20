"""The curated manifest, schema 3.

Source, not build output: a person commits these numbers, so the schema is what
catches a mistake before review does.
"""

import pytest
from pydantic import ValidationError

from modules.llm.catalog import (
    SCHEMA_VERSION,
    CuratedModelsManifest,
    load_curated_models,
)

pytestmark = pytest.mark.unit


def entry(**overrides) -> dict:
    """One well formed entry, before a test breaks a specific field."""
    base = {
        "model_id": "Qwen/Qwen3-8B",
        "family": "Qwen3",
        "label": "Qwen3 8B",
        "parameter_count": "8B",
        "shape": {
            "architecture": "qwen3",
            "block_count": 36,
            "head_count_kv": 8,
            "key_length": 128,
            "value_length": 128,
            "context_length": 40960,
            "n_vocab": 151936,
        },
        "capabilities": [],
        "decode_fraction": 1.0,
        "variants": [
            {
                "repo": "unsloth/Qwen3-8B-GGUF",
                "file": "Qwen3-8B-Q4_K_M.gguf",
                "quantization": "Q4_K_M",
                "size_bytes": 5027784512,
                "rank": 78,
                "rank_basis": "llmfit-1.1.11",
                "validated": True,
            }
        ],
    }
    return {**base, **overrides}


def manifest(models: list[dict] | None = None, **overrides) -> dict:
    """A whole manifest around one or more entries."""
    return {"schema_version": 3, "models": models or [entry()], **overrides}


def test_a_well_formed_manifest_loads() -> None:
    """The baseline, so the rejection tests cannot pass by rejecting everything."""
    parsed = CuratedModelsManifest.model_validate(manifest())

    assert parsed.models[0].variants[0].rank == 78
    assert parsed.models[0].shape.block_count == 36


def test_schema_two_is_refused_rather_than_read_as_three() -> None:
    """Silently reading a v2 entry would drop every shape and price nothing."""
    with pytest.raises(ValidationError, match="unsupported curated-model schema"):
        CuratedModelsManifest.model_validate(manifest() | {"schema_version": 2})


def test_an_entry_without_a_shape_is_refused() -> None:
    """Shape is what prices a curated row offline, on first paint, with no
    network. Without it the airgapped product has no badge on its only tier."""
    broken = entry()
    del broken["shape"]

    with pytest.raises(ValidationError):
        CuratedModelsManifest.model_validate(manifest([broken]))


def test_an_entry_must_ship_at_least_one_build() -> None:
    """A row with nothing to install is a row that can only disappoint."""
    with pytest.raises(ValidationError):
        CuratedModelsManifest.model_validate(manifest([entry(variants=[])]))


def test_a_rank_must_name_the_quantization_it_was_taken_at() -> None:
    """Quality is a function of (model, quantization): the same model reads
    75 / 78 / 81 / 82 / 83 across its ladder. A rank beside its own build cannot
    drift from the file it describes, which a top level field could not prevent.
    """
    variant = dict(entry()["variants"][0])
    del variant["quantization"]

    with pytest.raises(ValidationError):
        CuratedModelsManifest.model_validate(manifest([entry(variants=[variant])]))


def test_ranks_are_never_compared_across_different_bases() -> None:
    """An llmfit number and an eval derived number are not on one scale, and
    sorting them together would silently reorder the list."""
    mixed = [
        entry(),
        entry(
            model_id="Qwen/Qwen3-4B",
            label="Qwen3 4B",
            variants=[
                {
                    **entry()["variants"][0],
                    "file": "Qwen3-4B-Q4_K_M.gguf",
                    "rank": 63,
                    "rank_basis": "surfsense-eval-1",
                }
            ],
        ),
    ]

    with pytest.raises(ValidationError, match="rank_basis"):
        CuratedModelsManifest.model_validate(manifest(mixed))


def test_duplicate_model_ids_are_refused() -> None:
    """Two rows for one model is a copy paste slip, not a choice."""
    with pytest.raises(ValidationError, match="duplicate"):
        CuratedModelsManifest.model_validate(manifest([entry(), entry()]))


def test_two_entries_cannot_pin_the_same_file() -> None:
    """Two rows installing identical bytes is a copy paste slip, not a choice."""
    twin = entry(model_id="Qwen/Qwen3-8B-Other", label="Other")  # same repo + file

    with pytest.raises(ValidationError, match="duplicate"):
        CuratedModelsManifest.model_validate(manifest([entry(), twin]))


def test_the_superseded_v2_fields_are_refused_rather_than_ignored() -> None:
    """`minimum_fit` was a gate and only physics gates now. Leaving it readable
    would let a stale manifest look valid while meaning something else."""
    with pytest.raises(ValidationError):
        CuratedModelsManifest.model_validate(manifest([entry(minimum_fit="good")]))


def test_the_shipped_manifest_is_valid_and_prices_offline() -> None:
    """The one that actually ships, parsed as the app parses it."""
    parsed = load_curated_models()

    assert parsed.schema_version == SCHEMA_VERSION
    assert parsed.models
    for model in parsed.models:
        assert model.shape.block_count > 0
        assert model.variants
        for variant in model.variants:
            assert variant.rank > 0
            assert variant.quantization
