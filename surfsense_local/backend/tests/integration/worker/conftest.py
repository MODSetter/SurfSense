import pytest

from shared.config import get_search_settings


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
