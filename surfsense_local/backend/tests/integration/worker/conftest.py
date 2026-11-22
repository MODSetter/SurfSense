from typing import Any

import pytest

from modules.llm.profile import Fingerprint, Tier
from modules.llm.resolution import ResolvedGeneration, ResolvedImageGeneration

# Docling's reading of a file, scripted by the test.
from tests.integration.worker.docling_stand_in import (
    docling,  # noqa: F401 - a fixture
)

# Docling reading exactly the pages it is asked for.
from tests.integration.worker.paged_docling_stand_in import (
    paged_docling,  # noqa: F401 - a fixture
)

# The API's speech routes, as a recording's ingest job reaches them.
from tests.integration.worker.speech_api_stand_in import (
    speech_api,  # noqa: F401 - a fixture
)


@pytest.fixture
def stub_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the bundled model, so a pipeline test needs none on disk.

    Two seams reach for it: the chunker sizes to its tokenizer, and the
    embedder runs it. Chonkie's built-in character tokenizer replaces the
    first, a deterministic vector the second. Studio's role lookup is stubbed
    too, so a test fakes only the model call it cares about.
    """

    def embed(spec: Any, texts: list[str], _purpose: Any) -> list[list[float]]:
        # Distinct per text, so a misplaced chunk is a mismatched vector.
        return [[float(len(text) % 97)] * spec.dimension for text in texts]

    monkeypatch.setattr("modules.embedding.encoder.embed", embed)
    monkeypatch.setattr(
        "worker.ingestion.chunking._default_tokenizer", lambda: "character"
    )

    # Compact is what a bundled local model gets, so that is the path under test.
    selection = type(
        "Selection",
        (),
        {
            "provider": "fake",
            "name": "fake",
            "connection": None,
            "tier": Tier.COMPACT,
            "fingerprint": Fingerprint("fake", "fake"),
        },
    )()
    monkeypatch.setattr(
        "worker.studio.job.resolve_routed_generation",
        lambda _session: ResolvedGeneration(selection, None),
    )
    monkeypatch.setattr(
        "worker.studio.job.resolve_image_generation",
        lambda _session: ResolvedImageGeneration(selection, None),
    )
