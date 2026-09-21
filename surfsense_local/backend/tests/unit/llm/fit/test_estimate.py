"""The fit verdict, against llama.cpp's own fitter.

Reference numbers come from `common_params_fit_impl` under `-v` at b11050 on an
M2 / 8 GB, which prints what it projects and what margin it must leave.
"""

import pytest

from modules.llm.fit import (
    FitState,
    HardwareBudget,
    KvPrecision,
    ModelShape,
    estimate,
)

pytestmark = pytest.mark.unit

MIB = 1024**2

QWEN3_1_7B = ModelShape(
    architecture="qwen3",
    block_count=28,
    head_count_kv=8,
    key_length=128,
    value_length=128,
    context_length=40960,
    n_vocab=151936,
)
WEIGHTS = 1050 * MIB  # MTL0_Mapped model buffer, measured

# MTL0: 5461.3 MiB total, 5460 MiB free as the fitter saw it, on an 8 GiB
# machine. Two ceilings on one memory, not two pools: Metal will not allocate
# past its working set, and the CPU backend reads the same chips without that
# limit, which is why a projection above 5460 still loaded with layers spilled.
M2 = HardwareBudget(
    device_free_bytes=5460 * MIB,
    device_total_bytes=5461 * MIB,
    fit_reserve_bytes=1024 * MIB,
    ram_available_bytes=6144 * MIB,
    uma=True,
    has_gpu=True,
)

# An older laptop with no card ggml can use. Nothing to spill from, so the
# processor's memory is both where the model runs and all there is.
NO_GPU = HardwareBudget(
    device_free_bytes=0,
    device_total_bytes=0,
    fit_reserve_bytes=1024 * MIB,
    ram_available_bytes=14 * 1024 * MIB,
    uma=False,
    has_gpu=False,
)


def test_the_measured_resident_case_fits() -> None:
    """`projected to use 2944 MiB vs 5460 MiB free`, and it loaded 29/29."""
    verdict = estimate(QWEN3_1_7B, WEIGHTS, M2, n_ctx=16384)

    assert verdict.state is FitState.FITS
    assert verdict.offload_fraction == 0.0


def test_a_model_that_fits_in_free_memory_but_not_past_the_reserve_is_partial() -> None:
    """The regression a single collapsed `overhead` term gets backwards.

    `need` sits under raw free memory and over what --fit will actually use, so
    the two subtractions have to stay on opposite sides of the comparison.
    """
    shape = ModelShape(
        architecture="qwen3",
        block_count=28,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=40960,
        n_vocab=151936,
    )
    # 5000 MiB of need: below 5460 free, above 5460 - 1024 usable.
    weights = 5000 * MIB - estimate(shape, 0, M2, n_ctx=16384).need_bytes

    verdict = estimate(shape, weights, M2, n_ctx=16384)

    assert M2.device_free_bytes > verdict.need_bytes > M2.usable_vram_bytes
    assert verdict.state is FitState.PARTIAL


def test_the_measured_spilling_case_reports_how_much_went_to_the_cpu() -> None:
    """At -c 40960 the fitter projected 5752 MiB and settled on 23 of 29 layers."""
    verdict = estimate(QWEN3_1_7B, WEIGHTS, M2, n_ctx=40960)

    assert verdict.state is FitState.PARTIAL
    assert 0.0 < verdict.offload_fraction < 1.0


def test_a_model_over_vram_plus_ram_is_refused_by_physics() -> None:
    """The only state that blocks install, evaluated at the 16K floor."""
    huge = ModelShape(
        architecture="qwen3",
        block_count=64,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=40960,
        n_vocab=151936,
    )

    verdict = estimate(huge, 60_000 * MIB, M2, n_ctx=16384)

    assert verdict.state is FitState.TOO_BIG
    assert not verdict.can_install


def test_partial_installs_exactly_like_fits() -> None:
    """Only physics refuses. Reduced speed is a label, never a gate."""
    partial = estimate(QWEN3_1_7B, WEIGHTS, M2, n_ctx=40960)

    assert partial.state is FitState.PARTIAL
    assert partial.can_install


def test_quantizing_the_cache_can_turn_a_spill_into_residency() -> None:
    """This is why precision is an output of the fit calculation, not a default."""
    at_f16 = estimate(QWEN3_1_7B, WEIGHTS, M2, n_ctx=40960, precision=KvPrecision.F16)
    at_q8 = estimate(QWEN3_1_7B, WEIGHTS, M2, n_ctx=40960, precision=KvPrecision.Q8_0)

    assert at_f16.state is FitState.PARTIAL
    assert at_q8.state is FitState.FITS


def test_a_vision_projector_is_counted_because_the_fitter_does_not() -> None:
    """llama.cpp issue #19980: `--fit` does not account for mmproj memory, so a
    vision model that our sum says fits can still fail to allocate. We add the
    projector's bytes to `need` rather than trusting the fitter to.
    """
    text_only = estimate(QWEN3_1_7B, WEIGHTS, M2, n_ctx=16384)
    with_projector = estimate(
        QWEN3_1_7B, WEIGHTS, M2, n_ctx=16384, mmproj_bytes=600 * MIB
    )

    assert with_projector.need_bytes == text_only.need_bytes + 600 * MIB


def test_a_projector_can_be_what_tips_a_model_over() -> None:
    """Which is the whole point of counting it."""
    resident = estimate(QWEN3_1_7B, 2400 * MIB, M2, n_ctx=16384)
    with_projector = estimate(
        QWEN3_1_7B, 2400 * MIB, M2, n_ctx=16384, mmproj_bytes=900 * MIB
    )

    assert resident.state is FitState.FITS
    assert with_projector.state is FitState.PARTIAL


def test_without_a_gpu_a_model_inside_memory_simply_fits() -> None:
    """The measured bug: every row on a CPU only machine read `Reduced speed`.

    There is no graphics card to be too big for, so a model that fits in memory
    runs, at the only speed this machine has. Calling that a partial offload
    described a spill from a device the machine does not have, and the badge
    named hardware the user could see they did not own.
    """
    verdict = estimate(QWEN3_1_7B, WEIGHTS, NO_GPU, n_ctx=16384)

    assert verdict.state is FitState.FITS
    assert verdict.offload_fraction == 0.0


def test_without_a_gpu_the_middle_state_is_unreachable() -> None:
    """Swept rather than sampled: partial means some layers moved to the CPU,
    and on this machine every layer was already there."""
    for gib in range(1, 40):
        state = estimate(QWEN3_1_7B, gib * 1024 * MIB, NO_GPU).state

        assert state in {FitState.FITS, FitState.TOO_BIG}


def test_without_a_gpu_physics_still_refuses_what_memory_cannot_hold() -> None:
    """The one refusal that survives: a model larger than the machine."""
    verdict = estimate(QWEN3_1_7B, 20 * 1024 * MIB, NO_GPU)

    assert verdict.state is FitState.TOO_BIG
    assert verdict.budget_bytes == NO_GPU.ram_available_bytes


def test_unified_memory_refuses_past_the_pool_not_past_the_pool_twice_over() -> None:
    """The measured bug: one memory counted as two.

    An 8 GB Mac was priced with a 10.3 GB refusal threshold, because the working
    set and the host reading, which describe the same chips, were added. A model
    between the pool and that sum was offered to a machine that cannot hold it.
    """
    need = estimate(QWEN3_1_7B, 5000 * MIB, M2).need_bytes

    assert need > M2.device_free_bytes
    assert estimate(QWEN3_1_7B, 5000 * MIB, M2).state is FitState.TOO_BIG
