"""The four terms a load allocates, and that they still add up.

A single `need` number can be right for compensating wrong reasons. Naming the
parts is what makes each one assertable on its own.
"""

import pytest

from modules.llm.fit import KvPrecision, ModelShape, estimate, itemise
from modules.llm.fit.budget import HardwareBudget

pytestmark = pytest.mark.unit

MIB = 1024**2

QWEN3_4B = ModelShape(
    architecture="qwen3",
    block_count=36,
    head_count_kv=8,
    key_length=128,
    value_length=128,
    context_length=40960,
    n_vocab=151936,
    embedding_length=2560,
    feed_forward_length=9728,
)
ROOMY = HardwareBudget(24000 * MIB, 24576 * MIB, 1024 * MIB, 32000 * MIB, False, True)


def test_the_parts_are_what_the_verdict_compares() -> None:
    """The property that keeps the itemisation honest: if these ever stop
    summing to `need`, one of the two is describing a different model."""
    for n_ctx in (8192, 16384, 40960):
        items = itemise(QWEN3_4B, 2500 * MIB, n_ctx)
        verdict = estimate(QWEN3_4B, 2500 * MIB, ROOMY, n_ctx=n_ctx)

        assert items.total == verdict.need_bytes


def test_the_weights_term_does_not_move_with_the_window() -> None:
    """The load bearing one. Weights and cache are priced by different modules,
    and a window that moved the weights would mean the two had started naming
    the same bytes."""
    narrow = itemise(QWEN3_4B, 2500 * MIB, 8192)
    wide = itemise(QWEN3_4B, 2500 * MIB, 40960)

    assert narrow.weights_bytes == wide.weights_bytes
    assert wide.kv_bytes > narrow.kv_bytes


def test_the_projector_is_its_own_term() -> None:
    """`--fit` does not count it, and the fitter cannot move it either, so it is
    neither part of the weights nor part of what a layer costs."""
    items = itemise(QWEN3_4B, 2500 * MIB, 16384, mmproj_bytes=600 * MIB)

    assert items.mmproj_bytes == 600 * MIB
    assert items.weights_bytes == 2500 * MIB


def test_a_quantized_cache_moves_only_the_cache_term() -> None:
    """Which is why precision is an output of the fit calculation."""
    f16 = itemise(QWEN3_4B, 2500 * MIB, 16384, KvPrecision.F16)
    q8 = itemise(QWEN3_4B, 2500 * MIB, 16384, KvPrecision.Q8_0)

    assert q8.kv_bytes < f16.kv_bytes
    assert q8.weights_bytes == f16.weights_bytes
    assert q8.compute_bytes == f16.compute_bytes
