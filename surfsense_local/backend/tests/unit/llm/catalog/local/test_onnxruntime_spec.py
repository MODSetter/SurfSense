"""A curated embedder as the spec an index stores."""

import pytest

from modules.embedding.bundled import BGE
from modules.llm.catalog.local.engines.onnxruntime.spec import spec_for
from modules.llm.catalog.local.manifest import load_local_manifest

pytestmark = pytest.mark.unit


def test_the_manifests_bge_is_the_bundled_spec() -> None:
    """Two statements of one model: the shipped files and the catalog row."""
    (model,) = [m for m in load_local_manifest().models if m.id == BGE.id]

    assert spec_for(model) == BGE


def test_every_curated_embedder_names_its_files_as_they_land() -> None:
    """One folder per model, so the upstream `onnx/` folder is dropped."""
    for model in load_local_manifest().models:
        if model.embedding is not None:
            spec = spec_for(model)
            assert "/" not in spec.weights.path and "/" not in spec.tokenizer.path
