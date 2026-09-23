"""What a fit verdict says to a person.

A badge is a warning, shown only when there is something to warn about. The
tiers a build can be recommended at carry none, so the star and a warning can
never sit on the same row.
"""

import pytest

from modules.llm.fit import (
    RECOMMENDABLE_TIERS,
    BadgeLevel,
    FitState,
    HardwareBudget,
    badge,
    speed_tier,
)
from modules.llm.fit.estimate import FitVerdict

pytestmark = pytest.mark.unit

MIB = 1024**2
DISCRETE = HardwareBudget(6000 * MIB, 8000 * MIB, 1024 * MIB, 16000 * MIB, False, True)
APPLE = HardwareBudget(5461 * MIB, 5461 * MIB, 1024 * MIB, 6144 * MIB, True, True)
NO_GPU = HardwareBudget(0, 0, 1024 * MIB, 16000 * MIB, False, False)
FRACTIONS = (0.1, 0.25, 0.35, 0.5, 0.7, 0.9)


def verdict(state: FitState, f: float = 0.0) -> FitVerdict:
    """A verdict needing 21 GB against 13.6 GB available."""
    return FitVerdict(state, 21 * 1000**3, 13_600_000_000, f)


def every_verdict():
    """Every state and spill a machine can produce."""
    for budget in (DISCRETE, APPLE, NO_GPU):
        for state in FitState:
            if state is FitState.PARTIAL and not budget.has_gpu:
                continue
            for fraction in FRACTIONS if state is FitState.PARTIAL else (0.0,):
                yield verdict(state, fraction), budget


def test_a_build_that_can_be_recommended_carries_no_warning() -> None:
    """The invariant the screen needs: never a star beside "Reduced speed"."""
    for fit, budget in every_verdict():
        level = badge(fit, budget).level
        recommendable = speed_tier(fit) in RECOMMENDABLE_TIERS
        assert (level is BadgeLevel.NONE) == recommendable, (fit, budget)


def test_a_build_that_runs_fully_says_nothing() -> None:
    """Full speed on every row is noise that hides the rows that matter. The
    hardware line already says where models run."""
    for budget in (DISCRETE, APPLE, NO_GPU):
        text = badge(verdict(FitState.FITS), budget)

        assert text.level is BadgeLevel.NONE
        assert text.verdict == ""
        assert text.reason == ""


def test_a_light_spill_is_explained_quietly_without_a_warning() -> None:
    """Recommended on purpose: measured, a quarter spilled runs without
    noticeable lag. It is described, not flagged."""
    text = badge(verdict(FitState.PARTIAL, 0.1), DISCRETE)

    assert text.level is BadgeLevel.NONE
    assert text.verdict == ""
    assert "Most of it" in text.reason


def test_heavier_spills_warn_and_read_differently() -> None:
    """Moderate and heavy spill share a verdict and differ in why."""
    middling = badge(verdict(FitState.PARTIAL, 0.35), DISCRETE)
    severe = badge(verdict(FitState.PARTIAL, 0.7), DISCRETE)

    assert middling.level is severe.level is BadgeLevel.NOTICE
    assert middling.verdict == severe.verdict == "Reduced speed"
    assert middling.reason != severe.reason


def test_the_bands_sit_where_the_spec_put_them() -> None:
    """A quarter and a half, not a single threshold between them."""
    assert badge(verdict(FitState.PARTIAL, 0.25), DISCRETE).level is BadgeLevel.NONE
    assert badge(verdict(FitState.PARTIAL, 0.3), DISCRETE).level is BadgeLevel.NOTICE
    assert (
        badge(verdict(FitState.PARTIAL, 0.5), DISCRETE).reason
        == badge(verdict(FitState.PARTIAL, 0.9), DISCRETE).reason
    )


def test_a_refusal_states_both_numbers() -> None:
    """Never a bare disabled control: say what it needs and what there is."""
    text = badge(verdict(FitState.TOO_BIG), DISCRETE)

    assert text.level is BadgeLevel.REFUSE
    assert text.verdict == "Won't fit"
    assert "21 GB" in text.reason
    assert "13.6 GB" in text.reason


def test_apple_silicon_is_never_told_about_system_ram() -> None:
    """There is no separate pool to spill into, so no transfer to describe."""
    for fraction in FRACTIONS:
        text = badge(verdict(FitState.PARTIAL, fraction), APPLE)

        assert "system RAM" not in text.reason
        assert "graphics card" not in text.reason
        assert "processor" not in text.reason


def test_no_user_facing_string_uses_an_em_dash_or_a_hyphen() -> None:
    """A standing copy rule. Commas, full stops, parentheses."""
    for fit, budget in every_verdict():
        text = badge(fit, budget)
        assert "—" not in text.verdict + text.reason
        assert "-" not in text.verdict + text.reason
