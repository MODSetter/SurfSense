"""The curated local manifest: evidence, pinned file sets, reviewed defaults.

Source, not build output: a script writes it and a person reviews the diff, so
the schema is what catches a mistake before review does.
"""

import copy

import pytest
from pydantic import ValidationError

from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import FileRole
from modules.llm.catalog.local.manifest import (
    SCHEMA_VERSION,
    LocalManifest,
    load_local_manifest,
)

pytestmark = pytest.mark.unit

SHA = "a" * 64
REV = "3f2a" + "0" * 36


def file(role: str, path: str, size: int, **extra) -> dict:
    """One pinned file, as the refresh script writes it."""
    return {
        "role": role,
        "repo": "unsloth/gemma-3-4b-it-GGUF",
        "upstream_repo": None,
        "revision": REV,
        "path": path,
        "size_bytes": size,
        "sha256": SHA,
        **extra,
    }


PROJECTOR = file(
    "projector",
    "mmproj-F16.gguf",
    850,
    gguf={"general.type": "mmproj", "clip.has_vision_encoder": True},
)


def entry(**overrides) -> dict:
    """One well formed entry, before a test breaks a field."""
    base = {
        "id": "gemma-3-4b",
        "name": "Gemma 3 4B",
        "family": "Gemma 3",
        "publisher": "Google",
        "description": "Small chat model that reads images",
        "license": "gemma",
        "source_repo": "google/gemma-3-4b-it",
        "aliases": ["google/gemma-3-4b-it"],
        "evidence": {
            "architecture": "gemma3",
            "pipeline_tag": "image-text-to-text",
            "parameters_b": 3.9,
        },
        "context": 131072,
        "template": {"tools": False, "reasoning": False, "system_role": True},
        "sampling": None,
        "image": None,
        "shape": {
            "block_count": 34,
            "head_count_kv": 4,
            "key_length": 256,
            "value_length": 256,
            "n_vocab": 262144,
            "embedding_length": 2560,
            "feed_forward_length": 10240,
        },
        "builds": [
            {
                "quantization": "Q4_K_M",
                "files": [
                    file("weights", "gemma-3-4b-it-Q4_K_M.gguf", 2_490),
                    PROJECTOR,
                ],
                "run": {"args": []},
                "validated": {"llama_cpp": None},
            },
            {
                "quantization": "UD-Q4_K_XL",
                "files": [
                    file("weights", "gemma-3-4b-it-UD-Q4_K_XL.gguf", 2_540),
                    PROJECTOR,
                ],
                "run": {"args": []},
                "validated": {"llama_cpp": "b6500"},
            },
        ],
    }
    return {**base, **overrides}


def manifest(*models: dict) -> dict:
    """A whole manifest around the given entries."""
    return {
        "schema_version": SCHEMA_VERSION,
        "refreshed_at": "2026-09-23",
        "models": list(models) or [entry()],
    }


def test_a_well_formed_manifest_loads() -> None:
    """A well formed manifest loads."""
    parsed = LocalManifest.model_validate(manifest())

    (model,) = parsed.models
    assert model.id == "gemma-3-4b"
    assert model.model_shape.architecture == "gemma3"
    assert model.model_shape.context_length == 131072


def test_a_build_is_the_same_object_search_produces() -> None:
    """Curated and searched builds share one shape, so every reader of a build,
    the badge, fit, the downloader, never asks where it came from."""
    model = LocalManifest.model_validate(manifest()).models[0]

    build = model.as_builds()[1]
    assert build.quantization == "UD-Q4_K_XL"
    assert build.projector is not None and build.projector.role is FileRole.PROJECTOR
    assert build.projector.gguf["clip.has_vision_encoder"] is True
    assert build.footprint_bytes == 2_540 + 850
    assert build.weights.revision == REV


def test_every_file_is_pinned_and_verifiable() -> None:
    """Every file is pinned and verifiable."""
    for key, bad in (("revision", "main"), ("sha256", "abc"), ("size_bytes", 0)):
        broken = entry()
        broken["builds"][0]["files"][0][key] = bad
        with pytest.raises(ValidationError):
            LocalManifest.model_validate(manifest(broken))


def test_a_build_needs_weights_and_at_most_one_projector() -> None:
    """A build needs weights and at most one projector."""
    no_weights = entry()
    no_weights["builds"][0]["files"] = [PROJECTOR]
    two_projectors = entry()
    two_projectors["builds"][0]["files"].append(copy.deepcopy(PROJECTOR))

    for broken in (no_weights, two_projectors):
        with pytest.raises(ValidationError):
            LocalManifest.model_validate(manifest(broken))


def test_ids_and_quantizations_do_not_repeat() -> None:
    """Ids and quantizations do not repeat."""
    with pytest.raises(ValidationError):
        LocalManifest.model_validate(manifest(entry(), entry()))

    doubled = entry()
    doubled["builds"][1]["quantization"] = "Q4_K_M"
    with pytest.raises(ValidationError):
        LocalManifest.model_validate(manifest(doubled))


def test_a_label_carries_no_score() -> None:
    """Preference is list position and nothing else."""
    for field in ("score", "quality", "rank"):
        with pytest.raises(ValidationError):
            LocalManifest.model_validate(manifest(entry(**{field: 1})))


def test_the_shipped_manifest_loads() -> None:
    """The shipped manifest loads."""
    shipped = load_local_manifest()

    assert shipped.schema_version == SCHEMA_VERSION
    assert shipped.models
    for model in shipped.models:
        assert model.builds
