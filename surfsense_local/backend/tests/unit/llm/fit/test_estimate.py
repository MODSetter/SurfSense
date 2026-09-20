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

# MTL0: 5461.3 MiB total, 5460 MiB free as the fitter saw it.
M2 = HardwareBudget(
    device_free_bytes=5460 * MIB,
    device_total_bytes=5461 * MIB,
    fit_reserve_bytes=1024 * MIB,
    ram_available_bytes=2000 * MIB,
    uma=True,
    has_gpu=True,
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
