"""What a model SurfSense did not measure is told when it fails its check."""

import pytest

from modules.embedding import verify as verify_module
from modules.embedding.bundled import BGE
from modules.embedding.search_check import SearchCheck
from modules.embedding.verify import Refusal, verify

pytestmark = pytest.mark.unit


def _checked(monkeypatch: pytest.MonkeyPatch, first: int, asked: int) -> None:
    monkeypatch.setattr(verify_module, "width", lambda spec, probe: 384)
    monkeypatch.setattr(
        verify_module,
        "search_check",
        lambda queries, passages: SearchCheck(first, asked),
    )


def test_a_miss_is_refused_with_its_counts_beside_the_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sentence is the fallback; the counts go raw for an interface that
    words the refusal itself."""
    _checked(monkeypatch, 7, 10)

    width, refusal = verify(BGE)

    assert width == 384
    assert refusal == Refusal(
        "It found 7 of 10 answers first; a search model has to find all 10.",
        found=7,
        asked=10,
    )


def test_a_model_that_finds_every_answer_is_not_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The width the probe measured comes back with nothing beside it."""
    _checked(monkeypatch, 10, 10)

    assert verify(BGE) == (384, None)
