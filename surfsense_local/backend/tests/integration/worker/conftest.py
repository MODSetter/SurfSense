from collections.abc import Iterator
from pathlib import Path

import pytest

from shared.config import get_search_settings

# Where scripts/fetch_embedding_model.py places the model for development and CI.
REAL_MODELS = Path.home() / ".surfsense" / "models"


@pytest.fixture
def stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the bundled model, so a pipeline test needs none on disk.

    Two seams reach for it: the chunker sizes to its tokenizer, and the
    embedder runs it. Chonkie's built-in character tokenizer replaces the
    first, a deterministic vector the second.
    """
    width = get_search_settings().embedding_dimension

    def embed(texts: list[str]) -> list[list[float]]:
        # Distinct per text, so a misplaced chunk is a mismatched vector.
        return [[float(len(text) % 97)] * width for text in texts]

    monkeypatch.setattr("worker.ingestion.embedding.embed", embed)
    monkeypatch.setattr(
        "worker.ingestion.chunking._default_tokenizer", lambda: "character"
    )


@pytest.fixture
def real_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point ingest at the model fetch_embedding_model.py downloaded, or skip."""
    onnx = REAL_MODELS / "bge-small-en-v1.5" / "model_optimized.onnx"
    if not onnx.is_file():
        pytest.skip("run scripts/fetch_embedding_model.py to exercise the real encoder")

    monkeypatch.setenv("SURFSENSE_LOCAL_MODELS_DIR", str(REAL_MODELS))
    yield REAL_MODELS
