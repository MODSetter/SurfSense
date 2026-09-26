"""Properties the estimator has to hold whatever it is asked.

The tests beside this one assert numbers, which a self-consistent wrong
estimator can also satisfy. These assert relationships instead, over a grid of
shapes, windows, precisions and machines, and they are the kind of check that
would have caught both of the verdict bugs this work started from: one of them
priced a machine with no GPU as spilling, and the other added a unified memory
pool to itself.

Borrowed in design from Unsloth Studio's platform matrix, which asks the same
question: not "is the number N", but "is this estimator internally honest".
"""

from itertools import pairwise

import pytest

from modules.llm.fit import (
    CONTEXT_FLOOR_TOKENS,
    FitState,
    HardwareBudget,
    KvPrecision,
    ModelShape,
    estimate,
    itemise,
)
from modules.llm.hardware import BudgetMode, build_budget

pytestmark = pytest.mark.unit

MIB = 1024**2
GB = 1000**3

SHAPES = {
    "qwen3-1.7b": ModelShape(
        "qwen3", 28, 8, 128, 128, 40960, 151936,
        embedding_length=2048, feed_forward_length=6144,
    ),
    "qwen3-4b": ModelShape(
        "qwen3", 36, 8, 128, 128, 40960, 151936,
        embedding_length=2560, feed_forward_length=9728,
    ),
    "gemma3-swa": ModelShape(
        "gemma3", 48, 8, 128, 128, 131072, 262144,
        sliding_window=1024, embedding_length=3840, feed_forward_length=15360,
    ),
    "deepseek-mla": ModelShape(
        "deepseek2", 28, 1, 192, 128, 163840, 129280,
        embedding_length=2048, feed_forward_length=10944,
        kv_lora_rank=512, key_length_mla=64,
    ),
}

BUDGETS = {
    # A 6 GB card with the host behind it: the only shape where residency and
    # physics are genuinely two different pools.
    "discrete-6gb": HardwareBudget(5234 * MIB, 6002 * MIB, 1024 * MIB, 22750 * MIB, False, True),
    "discrete-24gb": HardwareBudget(23000 * MIB, 24576 * MIB, 1024 * MIB, 32000 * MIB, False, True),
    # Unified memory states one pool twice, which is what `build_budget` now
    # guarantees and what the second verdict bug got wrong.
    "unified-8gb": HardwareBudget(5222 * MIB, 5461 * MIB, 1024 * MIB, 5222 * MIB, True, True),
    "no-gpu-16gb": HardwareBudget(0, 0, 1024 * MIB, 14 * 1024 * MIB, False, False),
    # What a machine with no staged runtime produces.
    "probed-empty": build_budget([], 8 * 1024 * MIB, mode=BudgetMode.CAPACITY),
}

WINDOWS = (8192, 16384, 16385, 32768, 131072)
PRECISIONS = (KvPrecision.F16, KvPrecision.Q8_0)
WEIGHTS = (int(0.4 * GB), int(2.5 * GB), int(9.0 * GB), int(19.76 * GB))

EVERY_CASE = [
    (shape_name, budget_name, n_ctx, precision, weights)
    for shape_name in SHAPES
    for budget_name in BUDGETS
    for n_ctx in WINDOWS
    for precision in PRECISIONS
    for weights in WEIGHTS
]


@pytest.mark.parametrize(("shape_name", "budget_name", "n_ctx", "precision", "weights"), EVERY_CASE)
def test_the_itemisation_sums_to_what_the_verdict_reports(
    shape_name, budget_name, n_ctx, precision, weights
) -> None:
    """If these diverge, one of the two is describing a different model."""
    shape = SHAPES[shape_name]
    items = itemise(shape, weights, n_ctx, precision)
    verdict = estimate(SHAPES[shape_name], weights, BUDGETS[budget_name], n_ctx=n_ctx, precision=precision)

    assert items.total == verdict.need_bytes


@pytest.mark.parametrize(("shape_name", "budget_name", "n_ctx", "precision", "weights"), EVERY_CASE)
def test_nothing_is_ever_negative(
    shape_name, budget_name, n_ctx, precision, weights
) -> None:
    """A negative byte count is a subtraction that went the wrong way, and it
    would reach the screen as a badge claiming a model needs less than nothing.
    """
    verdict = estimate(SHAPES[shape_name], weights, BUDGETS[budget_name], n_ctx=n_ctx, precision=precision)

    assert verdict.need_bytes >= 0
    assert verdict.budget_bytes >= 0
    assert 0.0 <= verdict.offload_fraction <= 1.0


@pytest.mark.parametrize("shape_name", SHAPES)
@pytest.mark.parametrize("precision", PRECISIONS)
def test_the_weights_term_never_moves_with_the_window(shape_name, precision) -> None:
    """The load bearing one. Weights and cache are priced by separate modules,
    and a window that moved the weights would mean they had started naming the
    same bytes."""
    shape = SHAPES[shape_name]
    at_each = [itemise(shape, 2500 * MIB, n_ctx, precision) for n_ctx in WINDOWS]

    assert len({items.weights_bytes for items in at_each}) == 1


@pytest.mark.parametrize("shape_name", SHAPES)
@pytest.mark.parametrize("precision", PRECISIONS)
def test_cache_and_scratch_never_shrink_as_the_window_grows(shape_name, precision) -> None:
    """Both are sized from the window, so a wider one cannot cost less."""
    shape = SHAPES[shape_name]
    priced = [itemise(shape, 2500 * MIB, n_ctx, precision) for n_ctx in sorted(WINDOWS)]

    for narrower, wider in pairwise(priced):
        assert wider.kv_bytes >= narrower.kv_bytes
        assert wider.compute_bytes >= narrower.compute_bytes


@pytest.mark.parametrize("budget_name", BUDGETS)
def test_residency_is_never_more_generous_than_physics(budget_name) -> None:
    """Fitting entirely on the device is a stronger claim than merely being
    possible, so the budget it is measured against cannot be the larger one."""
    budget = BUDGETS[budget_name]

    assert budget.resident_bytes <= budget.refusal_bytes


@pytest.mark.parametrize(("shape_name", "n_ctx", "precision", "weights"),
    [(s, c, p, w) for s in SHAPES for c in WINDOWS for p in PRECISIONS for w in WEIGHTS])
def test_a_machine_with_no_gpu_never_reports_a_partial_offload(
    shape_name, n_ctx, precision, weights
) -> None:
    """The first verdict bug, as a property. There is no device to spill from,
    so every layer was already on the processor."""
    verdict = estimate(SHAPES[shape_name], weights, BUDGETS["no-gpu-16gb"], n_ctx=n_ctx, precision=precision)

    assert verdict.state in {FitState.FITS, FitState.TOO_BIG}
    assert verdict.offload_fraction in {0.0, 1.0}


@pytest.mark.parametrize(("shape_name", "n_ctx", "precision", "weights"),
    [(s, c, p, w) for s in SHAPES for c in WINDOWS for p in PRECISIONS for w in WEIGHTS])
def test_unified_memory_is_never_refused_later_than_its_own_pool(
    shape_name, n_ctx, precision, weights
) -> None:
    """The second verdict bug, as a property. The device reading and the host
    reading name one memory, so a refusal threshold above either of them is that
    memory counted twice."""
    budget = BUDGETS["unified-8gb"]
    verdict = estimate(SHAPES[shape_name], weights, budget, n_ctx=n_ctx, precision=precision)

    if verdict.state is FitState.TOO_BIG:
        assert verdict.budget_bytes <= budget.device_free_bytes


@pytest.mark.parametrize(("shape_name", "budget_name", "precision", "weights"),
    [(s, b, p, w) for s in SHAPES for b in BUDGETS for p in PRECISIONS for w in WEIGHTS])
def test_moving_work_off_the_device_never_shrinks_what_a_model_needs(
    shape_name, budget_name, precision, weights
) -> None:
    """An offloaded byte is not a freed byte. On unified memory in particular,
    a layer on the processor sits in the same chips it sat in before."""
    verdict = estimate(SHAPES[shape_name], weights, BUDGETS[budget_name], precision=precision)
    items = itemise(SHAPES[shape_name], weights, CONTEXT_FLOOR_TOKENS, precision)

    assert verdict.need_bytes == items.total
    assert verdict.need_bytes >= weights


def test_a_machine_with_no_staged_runtime_prices_against_the_host() -> None:
    """A probe that found nothing must not read as a device with no memory."""
    budget = BUDGETS["probed-empty"]

    assert budget.has_gpu is False
    assert budget.usable_vram_bytes == 0
    assert budget.resident_bytes == budget.ram_available_bytes


@pytest.mark.parametrize(("shape_name", "budget_name", "precision", "weights"),
    [(s, b, p, w) for s in SHAPES for b in BUDGETS for p in PRECISIONS for w in WEIGHTS])
def test_a_partial_offload_is_always_a_whole_number_of_layers(
    shape_name, budget_name, precision, weights
) -> None:
    """llama.cpp fills devices with whole layers, so a fraction that is not a
    multiple of one layer describes a placement the runtime cannot make."""
    shape = SHAPES[shape_name]
    verdict = estimate(shape, weights, BUDGETS[budget_name], precision=precision)
    if verdict.state is not FitState.PARTIAL:
        return

    layers = verdict.offload_fraction * shape.block_count

    assert layers == pytest.approx(round(layers))
