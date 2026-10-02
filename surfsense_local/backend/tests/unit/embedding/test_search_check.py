"""The bar a model SurfSense did not measure must clear: find the answer first."""

import numpy as np
import pytest

from modules.embedding.search_check import QUESTIONS, search_check

pytestmark = pytest.mark.unit


def test_a_model_that_finds_every_answer_first_passes() -> None:
    """Each question shares a direction with its answer and none with its decoy."""
    direction = {}
    for index, (question, answer, decoy) in enumerate(QUESTIONS):
        direction[question] = direction[answer] = index
        direction[decoy] = len(QUESTIONS) + index

    def embed(texts: list[str]) -> list[list[float]]:
        return [np.eye(2 * len(QUESTIONS))[direction[t]].tolist() for t in texts]

    result = search_check(embed)

    assert result.passed
    assert result.first == result.asked == len(QUESTIONS)


def test_a_model_that_cannot_tell_answer_from_decoy_fails() -> None:
    """A chat model served as an embedder ranks a same-topic decoy first."""
    rng = np.random.default_rng(0)

    def embed(texts: list[str]) -> list[list[float]]:
        return rng.normal(size=(len(texts), 16)).tolist()

    assert not search_check(embed).passed
