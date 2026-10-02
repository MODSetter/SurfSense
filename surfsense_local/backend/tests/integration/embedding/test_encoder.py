"""The encoder, run on the real bundled model."""

from pathlib import Path

import pytest

from modules.embedding.bundled import BGE
from modules.embedding.encoder import Purpose, embed
from modules.embedding.verify import verify

pytestmark = pytest.mark.integration

ASYMMETRIC = BGE.model_copy(update={"query_prefix": "query: "})


def test_a_query_prefix_applies_to_questions_only(real_model: Path) -> None:
    """Asymmetric models embed a question and a passage differently."""
    question = embed(ASYMMETRIC, ["when does the ship sail"], Purpose.QUERY)
    by_hand = embed(BGE, ["query: when does the ship sail"], Purpose.DOCUMENT)
    passage = embed(ASYMMETRIC, ["when does the ship sail"], Purpose.DOCUMENT)

    assert question == by_hand
    assert passage != question


def test_vectors_have_the_specs_width(real_model: Path) -> None:
    """The width the index's table is built for."""
    [vector] = embed(BGE, ["the ship sails at dawn"], Purpose.DOCUMENT)

    assert len(vector) == BGE.dimension


def test_a_real_search_model_passes_its_checks(real_model: Path) -> None:
    """What every Hugging Face pick runs after download, on a model that works.
    A config can misstate the width, so the probe's is the one kept."""
    misstated = BGE.model_copy(update={"dimension": 768})

    width, refusal = verify(misstated)

    assert (width, refusal) == (384, None)
