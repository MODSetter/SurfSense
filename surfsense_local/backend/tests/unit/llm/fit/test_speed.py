"""The one place `offload_fraction` becomes a decision.

Everything that turns a verdict into a person-facing choice (what the badge
says, whether the star shows) reads this instead of thresholding the raw
fraction itself, so two callers reading the same verdict cannot land on two
different, contradicting answers.
"""

import pytest

from modules.llm.fit.estimate import FitVerdict
from modules.llm.fit.speed import RECOMMENDABLE_TIERS, SpeedTier, speed_tier
from modules.llm.fit.states import FitState

pytestmark = pytest.mark.unit


def verdict(state: FitState, fraction: float = 0.0) -> FitVerdict:
    """A verdict needing 21 GB against 13.6 GB available."""
    return FitVerdict(state, 21 * 1000**3, 13_600_000_000, fraction)


def test_too_big_is_its_own_tier() -> None:
    """Physics refusing a build is a different fact from it merely spilling."""
    assert speed_tier(verdict(FitState.TOO_BIG)) is SpeedTier.TOO_BIG


def test_full_residency_is_the_top_tier() -> None:
    """Nothing spilled, so nothing here is a compromise."""
    assert speed_tier(verdict(FitState.FITS)) is SpeedTier.FULL


@pytest.mark.parametrize(
    ("fraction", "tier"),
    [
        (0.0, SpeedTier.LIGHT_SPILL),
        (0.1, SpeedTier.LIGHT_SPILL),
        (0.25, SpeedTier.LIGHT_SPILL),
        (0.26, SpeedTier.MODERATE_SPILL),
        (0.35, SpeedTier.MODERATE_SPILL),
        (0.5, SpeedTier.HEAVY_SPILL),
        (0.9, SpeedTier.HEAVY_SPILL),
    ],
)
def test_partial_splits_into_the_same_three_bands_the_badge_used_to_own(
    fraction: float, tier: SpeedTier
) -> None:
    """The exact boundaries `copy.py` used to threshold on its own: a quarter
    and a half. Moved here so nothing else can draw them differently."""
    assert speed_tier(verdict(FitState.PARTIAL, fraction)) is tier


def test_only_full_and_light_spill_are_recommendable() -> None:
    """The invariant this module exists for: a tier the star is allowed to use
    can never be one `copy.py` would describe as a compromise."""
    assert {SpeedTier.FULL, SpeedTier.LIGHT_SPILL} == RECOMMENDABLE_TIERS
