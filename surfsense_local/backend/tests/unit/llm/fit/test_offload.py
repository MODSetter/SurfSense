"""How much spills, counted the way llama.cpp actually places it.

The fitter fills a device with whole layers and stops at the last one that fits,
so the fraction is a count of layers rather than a ratio of bytes. It matters
because this number grades the reason line and gates the recommendation.
"""

import pytest

from modules.llm.fit import FitState, HardwareBudget, ModelShape, estimate
from modules.llm.fit.itemisation import itemise
from modules.llm.fit.offload import offload_fraction

pytestmark = pytest.mark.unit

MIB = 1024**2
GB = 1000**3

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

# The measured machine: RTX 3050, 5234 MiB free, llama.cpp's own 1024 MiB margin.
RTX_3050 = HardwareBudget(5234 * MIB, 6002 * MIB, 1024 * MIB, 22750 * MIB, False, True)


def test_the_measured_case_is_closer_in_layers_than_it_was_in_bytes() -> None:
    """Qwen3 4B spilled 602 MiB of weights plus 320 of cache on that card: 0.19.

    The byte ratio said 0.12, which is not a rounding error at thresholds of
    0.25 and 0.5. Counting layers gives 5 of 36.
    """
    verdict = estimate(QWEN3_4B, int(2.50 * GB), RTX_3050, n_ctx=16384)

    assert verdict.state is FitState.PARTIAL
    assert verdict.offload_fraction == pytest.approx(5 / 36)


def test_the_fraction_is_always_a_whole_number_of_layers() -> None:
    """A model cannot have four and a half layers on the processor."""
    for weights_gb in (2.4, 2.6, 3.0, 3.4, 4.0, 4.4):
        verdict = estimate(QWEN3_4B, int(weights_gb * GB), RTX_3050, n_ctx=16384)
        if verdict.state is not FitState.PARTIAL:
            continue

        layers = verdict.offload_fraction * QWEN3_4B.block_count

        assert layers == pytest.approx(round(layers))


def test_a_bigger_shortfall_spills_more_layers() -> None:
    """Monotonic, which is what lets the reason line be graded on it."""
    smaller = estimate(QWEN3_4B, int(2.6 * GB), RTX_3050, n_ctx=16384)
    larger = estimate(QWEN3_4B, int(4.0 * GB), RTX_3050, n_ctx=16384)

    assert larger.offload_fraction > smaller.offload_fraction


def test_a_model_that_fits_spills_nothing() -> None:
    """The boundary, stated rather than assumed."""
    items = itemise(QWEN3_4B, int(2.50 * GB), 16384)

    assert offload_fraction(QWEN3_4B, items, items.total) == 0.0


def test_only_layers_count_as_movable() -> None:
    """The projector is pinned by a flag and the compute buffer belongs to
    whichever device runs the graph, so neither is a thing the fitter can move.

    Counting them as movable would make each layer look larger than it is, and
    so under-count the layers a given shortfall displaces.
    """
    weights = int(2.50 * GB)
    without = itemise(QWEN3_4B, weights, 16384)
    with_projector = itemise(QWEN3_4B, weights, 16384, mmproj_bytes=600 * MIB)
    resident = without.total - 300 * MIB

    assert offload_fraction(QWEN3_4B, with_projector, resident) > offload_fraction(
        QWEN3_4B, without, resident
    )
