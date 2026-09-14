import pytest

from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration
from shared.config import get_search_settings


@pytest.fixture
def stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the bundled model, so a pipeline test needs none on disk.

    Two seams reach for it: the chunker sizes to its tokenizer, and the
    embedder runs it. Chonkie's built-in character tokenizer replaces the
    first, a deterministic vector the second. Studio's role lookup is stubbed
    too, so a test fakes only the model call it cares about.
    """
    width = get_search_settings().embedding_dimension

    def embed(texts: list[str]) -> list[list[float]]:
        # Distinct per text, so a misplaced chunk is a mismatched vector.
        return [[float(len(text) % 97)] * width for text in texts]

    monkeypatch.setattr("worker.ingestion.embedding.embed", embed)
    monkeypatch.setattr(
        "worker.ingestion.chunking._default_tokenizer", lambda: "character"
    )

    selection = type("Selection", (), {"provider": "fake", "name": "fake"})()
    monkeypatch.setattr(
        "worker.studio.job.resolve_generation",
        lambda _session: ResolvedGeneration(selection, None),
    )
    monkeypatch.setattr(
        "worker.studio.job.resolve_image_generation",
        lambda _session: ResolvedImageGeneration(selection, None),
    )
