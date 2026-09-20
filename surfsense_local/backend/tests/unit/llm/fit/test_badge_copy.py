"""What a fit verdict says to a person.

A badge is a verdict plus one plain line of why. The verdict is what someone
choosing a model needs; the mechanism is the explanation, not the headline.
"""

import pytest

from modules.llm.fit import FitState, HardwareBudget, badge
from modules.llm.fit.estimate import FitVerdict

pytestmark = pytest.mark.unit

MIB = 1024**2
DISCRETE = HardwareBudget(6000 * MIB, 8000 * MIB, 1024 * MIB, 16000 * MIB, False, True)
APPLE = HardwareBudget(5461 * MIB, 5461 * MIB, 1024 * MIB, 6144 * MIB, True, True)
NO_GPU = HardwareBudget(0, 0, 1024 * MIB, 16000 * MIB, False, False)


def verdict(state: FitState, f: float = 0.0) -> FitVerdict:
    """A verdict needing 21 GB against 13.6 GB available."""
    return FitVerdict(state, 21 * 1000**3, 13_600_000_000, f)


def test_no_user_facing_string_uses_an_em_dash_or_a_hyphen() -> None:
    """A standing copy rule for this phase. Commas, full stops, parentheses."""
    for budget in (DISCRETE, APPLE, NO_GPU):
        for state in FitState:
            if state is FitState.PARTIAL and not budget.has_gpu:
                continue
            text = badge(verdict(state), budget)
            assert "—" not in text.verdict + text.reason
            assert "-" not in text.verdict + text.reason


def test_full_speed_rather_than_fast() -> None:
    """Fast is a promise the badge cannot keep: a 32B on a 4090 is still slower
    than a 4B. Full speed is relative to the model, which is what the state means.
    """
    assert badge(verdict(FitState.FITS), DISCRETE).verdict == "Full speed"


def test_a_machine_with_no_gpu_is_told_it_works_not_that_it_is_fast() -> None:
    """Technically FITS, but "Full speed" reads as a boast about a slow situation
    when there is no faster alternative to contrast with."""
    assert badge(verdict(FitState.FITS), NO_GPU).verdict == "Works here"


def test_apple_silicon_is_never_told_about_system_ram() -> None:
    """There is no separate pool to spill into. Some layers run on the CPU
    backend against the same physical memory, so "uses system RAM" would
    describe a transfer that does not happen."""
    text = badge(verdict(FitState.PARTIAL, 0.3), APPLE)

    assert "system RAM" not in text.reason
    assert "graphics card" not in text.reason


def test_a_small_spill_and_a_large_one_do_not_get_the_same_sentence() -> None:
    """PARTIAL spans barely noticeable to unusable, and the fraction is already
    on the verdict. One sentence is wrong at both ends."""
    slight = badge(verdict(FitState.PARTIAL, 0.1), DISCRETE)
    severe = badge(verdict(FitState.PARTIAL, 0.7), DISCRETE)

    assert slight.verdict == severe.verdict == "Reduced speed"
    assert slight.reason != severe.reason


def test_a_refusal_states_both_numbers() -> None:
    """Never a bare disabled control: say what it needs and what there is."""
    text = badge(verdict(FitState.TOO_BIG), DISCRETE)

    assert text.verdict == "Won't fit"
    assert "21 GB" in text.reason
    assert "13.6 GB" in text.reason
