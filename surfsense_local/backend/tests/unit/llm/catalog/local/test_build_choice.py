"""Which build of a model to recommend on this machine."""

from dataclasses import dataclass

import pytest

from modules.llm.catalog.local.build_choice import default_build, recommended_build
from modules.llm.fit import SpeedTier

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class B:
    quantization: str
    footprint_bytes: int


Q3 = B("Q3_K_M", 3)
Q4 = B("Q4_K_M", 4)
UD4 = B("UD-Q4_K_XL", 5)
Q8 = B("Q8_0", 8)
F16 = B("F16", 16)
LADDER = [Q3, Q4, UD4, Q8, F16]


def tiers(**by_quant: SpeedTier):
    """A speed tier per quantization, full speed for any not named."""
    return lambda build: by_quant.get(
        build.quantization.replace("-", "_"), SpeedTier.FULL
    )


def test_the_default_is_the_first_preferred_quantization_present() -> None:
    """The default is the first preferred quantization present."""
    assert default_build(LADDER) is UD4
    assert default_build([Q3, Q8, F16]) is Q8
    assert default_build([F16, B("mystery", 1)]) is F16


def test_nothing_in_the_order_means_no_default() -> None:
    """Nothing in the order means no default."""
    assert default_build([B("unknown", 7)]) is None
    assert default_build([]) is None


def test_the_default_is_recommended_where_it_runs_well() -> None:
    """The default is recommended where it runs well."""
    assert recommended_build(LADDER, UD4, tiers()) is UD4


def test_spare_memory_never_recommends_above_the_default() -> None:
    """On a large card F16 fits too; recommending it would cost several times the
    download for little gain."""
    assert recommended_build(LADDER, UD4, lambda _: SpeedTier.FULL) is UD4


def test_a_default_that_runs_slowly_steps_down_to_the_largest_that_runs_well() -> None:
    """A default that runs slowly steps down to the largest that runs well."""
    choose = tiers(UD_Q4_K_XL=SpeedTier.MODERATE_SPILL, Q4_K_M=SpeedTier.LIGHT_SPILL)

    assert recommended_build(LADDER, UD4, choose) is Q4


def test_the_step_down_skips_what_would_still_be_slow() -> None:
    """The step down skips what would still be slow."""
    choose = tiers(
        UD_Q4_K_XL=SpeedTier.TOO_BIG,
        Q4_K_M=SpeedTier.HEAVY_SPILL,
    )

    assert recommended_build(LADDER, UD4, choose) is Q3


def test_nothing_fast_enough_means_no_recommendation() -> None:
    """Nothing fast enough means no recommendation."""
    assert recommended_build(LADDER, UD4, lambda _: SpeedTier.HEAVY_SPILL) is None


def test_no_default_means_no_recommendation() -> None:
    """No default means no recommendation."""
    assert recommended_build(LADDER, None, lambda _: SpeedTier.FULL) is None
