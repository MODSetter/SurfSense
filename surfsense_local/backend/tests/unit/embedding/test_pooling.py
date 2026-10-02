"""Turning a model's per-token output into one vector per text."""

import numpy as np
import pytest

from modules.embedding.pooling import pool
from modules.embedding.spec import Pooling

pytestmark = pytest.mark.unit

# Two texts, three token positions, width two. The second text has one pad token.
OUTPUT = np.array(
    [
        [[1.0, 0.0], [3.0, 2.0], [5.0, 4.0]],
        [[2.0, 2.0], [4.0, 6.0], [9.0, 9.0]],
    ]
)
MASK = np.array([[1, 1, 1], [1, 1, 0]])


def test_cls_takes_the_first_token() -> None:
    """bge and granite pool on the first token."""
    assert pool(Pooling.CLS, OUTPUT, MASK).tolist() == [[1.0, 0.0], [2.0, 2.0]]


def test_mean_averages_only_the_real_tokens() -> None:
    """A pad token is not part of the text."""
    assert pool(Pooling.MEAN, OUTPUT, MASK).tolist() == [[3.0, 2.0], [3.0, 4.0]]


def test_last_takes_each_texts_own_last_token() -> None:
    """Padding sits on the right, so the last real token moves per text."""
    assert pool(Pooling.LAST, OUTPUT, MASK).tolist() == [[5.0, 4.0], [4.0, 6.0]]


def test_a_build_that_pools_itself_is_left_alone() -> None:
    """Its output is already one vector per text."""
    pooled = np.array([[1.0, 2.0], [3.0, 4.0]])

    assert pool(Pooling.IN_MODEL, pooled, MASK).tolist() == pooled.tolist()
