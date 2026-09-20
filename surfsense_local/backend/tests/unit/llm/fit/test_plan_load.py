"""What we hand the runtime at load: a window and a cache precision.

Both are outputs of the fit calculation rather than defaults, because on a small
card the choice is what decides whether the model is resident at all.
"""

import pytest

from modules.llm.fit import (
    CONTEXT_FLOOR_TOKENS,
    FitState,
    HardwareBudget,
    KvPrecision,
    ModelShape,
    plan_load,
)

pytestmark = pytest.mark.unit

MIB = 1024**2
QWEN3_1_7B = ModelShape("qwen3", 28, 8, 128, 128, 40960, 151936)


def budget(free_mib: int) -> HardwareBudget:
    """A unified-memory device with llama.cpp's own one GiB margin."""
    return HardwareBudget(free_mib * MIB, free_mib * MIB, 1024 * MIB, 2000 * MIB, True, True)


def test_a_roomy_machine_keeps_the_lossless_cache() -> None:
    """f16 needs no flash-attention kernel, so it is preferred when it fits."""
    plan = plan_load(QWEN3_1_7B, 1050 * MIB, budget(5460))

    assert plan.precision is KvPrecision.F16
    assert plan.verdict.state is FitState.FITS


def test_precision_drops_only_when_it_buys_residency() -> None:
    """The measured case: f16 at 16K cannot allocate on a 6 GB card, q8_0 runs.

    Quality is lossless either way, so the cost is a flash-attention dependency
    we take on only where it converts a spill into residency.
    """
    plan = plan_load(QWEN3_1_7B, 2600 * MIB, budget(5460))

    assert plan.precision is KvPrecision.Q8_0
    assert plan.verdict.state is FitState.FITS


def test_the_window_never_drops_below_the_floor() -> None:
    """3000 history tokens plus roughly 8000 of grounding plus a reply.

    llama.cpp would reduce context to 4096 on its own if we left it unset, well
    under what a grounded turn needs, so the floor is ours to hold.
    """
    plan = plan_load(QWEN3_1_7B, 4200 * MIB, budget(5460))

    assert plan.n_ctx == CONTEXT_FLOOR_TOKENS
    assert plan.verdict.state is FitState.PARTIAL


def test_the_window_never_exceeds_what_the_model_was_trained_for() -> None:
    """Capped at the model's own context_length, however much memory there is."""
    plan = plan_load(QWEN3_1_7B, 1050 * MIB, budget(64000))

    assert plan.n_ctx == QWEN3_1_7B.context_length


def test_a_roomy_machine_widens_the_window_rather_than_leaving_it_at_the_floor() -> None:
    """Headroom buys conversation memory, which is the thing a user notices."""
    plan = plan_load(QWEN3_1_7B, 1050 * MIB, budget(8000))

    assert plan.n_ctx > CONTEXT_FLOOR_TOKENS
    assert plan.verdict.state is FitState.FITS


def test_a_model_trained_narrower_than_the_floor_is_not_stretched_past_it() -> None:
    """The floor and the cap conflict below 16K, and the cap has to win.

    Found end to end: SmolLM2 135M declares `context_length` 8192 and the plan
    asked for 16384, which is a window the model was never trained for. The floor
    says what a grounded turn needs; it cannot say what a model can do.
    """
    smol = ModelShape("llama", 30, 3, 64, 64, 8192, 49152)

    plan = plan_load(smol, 100 * MIB, budget(5460))

    assert plan.n_ctx == 8192


def test_the_floor_is_attempted_whatever_is_free_right_now() -> None:
    """The verdict must match the badge the catalog showed, which is priced
    against capacity. A machine that is busy this second has not become one that
    cannot run the model, and saying so after the user installed it would be the
    catalog contradicting itself.
    """
    capacity = HardwareBudget(5460 * MIB, 5460 * MIB, 1024 * MIB, 6144 * MIB, True, True)
    nearly_nothing = HardwareBudget(600 * MIB, 5460 * MIB, 1024 * MIB, 600 * MIB, True, True)

    plan = plan_load(QWEN3_1_7B, 1050 * MIB, capacity, live=nearly_nothing)

    assert plan.n_ctx == CONTEXT_FLOOR_TOKENS
    assert plan.verdict.state is FitState.FITS


def test_widening_past_the_floor_respects_what_is_actually_free() -> None:
    """Extra context is opportunistic, and on unified memory it is spent out of
    the same pool the OS is using. Taking 3.1 GB of cache to hold 28k tokens on
    a machine with 2.3 GB free is what made a load take 43 seconds.
    """
    capacity = HardwareBudget(5460 * MIB, 5460 * MIB, 1024 * MIB, 6144 * MIB, True, True)
    live = HardwareBudget(1900 * MIB, 5460 * MIB, 1024 * MIB, 1900 * MIB, True, True)

    roomy = plan_load(QWEN3_1_7B, 1050 * MIB, capacity)
    constrained = plan_load(QWEN3_1_7B, 1050 * MIB, capacity, live=live)

    assert roomy.n_ctx > constrained.n_ctx
    assert constrained.n_ctx == CONTEXT_FLOOR_TOKENS
