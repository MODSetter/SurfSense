"""The curated manifest, schema 4.

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
            "embedding_length": 4096,
            "feed_forward_length": 12288,
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
                "rank_basis": "surfsense-curated-1",
                "validated": True,
            }
        ],
    }
    return {**base, **overrides}


def manifest(models: list[dict] | None = None, **overrides) -> dict:
    """A whole manifest around one or more entries."""
    return {"schema_version": SCHEMA_VERSION, "models": models or [entry()], **overrides}


def test_a_well_formed_manifest_loads() -> None:
    """The baseline, so the rejection tests cannot pass by rejecting everything."""
    parsed = CuratedModelsManifest.model_validate(manifest())

    assert parsed.models[0].variants[0].rank == 78
    assert parsed.models[0].shape.block_count == 36


def test_an_older_schema_is_refused_rather_than_read_as_this_one() -> None:
    """Silently reading a v3 entry would leave the compute widths unset, and the
    scratch term would price every model as though it had nothing to compute."""
    with pytest.raises(ValidationError, match="unsupported curated-model schema"):
        CuratedModelsManifest.model_validate(manifest() | {"schema_version": 3})


def test_a_shape_without_the_widths_a_compute_buffer_needs_is_refused() -> None:
    """Optional on `ModelShape`, required here. A committed entry was authored
    by a script that read a real header, so a missing width is a manifest edited
    by hand, and the badge it produces would be confident and wrong."""
    shape = entry()["shape"]
    del shape["embedding_length"]

    with pytest.raises(ValidationError, match="embedding_length"):
        CuratedModelsManifest.model_validate(manifest(models=[entry(shape=shape)]))


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
    """Two rank scales are not on one scale, and sorting them together
    would silently reorder the list."""
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
        # The widths the scratch estimate is sized from. A regenerated manifest
        # that dropped them would price every row against one constant again.
        assert model.shape.embedding_length > 0
        assert model.shape.feed_forward_length > 0
        assert model.variants
        for variant in model.variants:
            assert variant.rank > 0
            assert variant.quantization


def test_every_shipped_entry_reaches_the_estimator_as_a_shape() -> None:
    """The property the catalog calls on first paint. A list field arriving from
    JSON has to become a tuple, because the shape it feeds is frozen."""
    for model in load_curated_models().models:
        shape = model.model_shape

        assert isinstance(shape.sliding_window_layers, tuple)
        assert shape.embedding_length == model.shape.embedding_length
