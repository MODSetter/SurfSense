"""The smoke case's date check: the sweep stops a model that fails smoke, so the date's spelling must not decide it."""

import pytest

from tests.live.test_smoke import says_the_move_day

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "answer",
    [
        "The Bergen depot moves on Monday 16 November 2026.",
        "It moves on Monday, November 16, 2026.",
        "It moves on Monday, November 16th, 2026.",
        "The move is on November 16th.",
        "It moves on the 16th of November.",
        "It moves on 16th November 2026.",
        "Am 16. November 2026.",
        "It moves on Nov 16.",
        "It moves on Nov. 16, 2026.",
        "It moves on 16 Nov 2026.",
        "It moves on 2026-11-16.",
        "It moves on 16/11/2026.",
        "It moves on 11/16/2026.",
        "It moves on monday 16 november.",
    ],
)
def test_the_move_day_is_taken_in_any_common_spelling(answer: str) -> None:
    """Day first or month first, ordinal or not, abbreviated, numeric, any case."""
    assert says_the_move_day(answer)


@pytest.mark.parametrize(
    "answer",
    [
        "The old yard closes for good on 20 November.",
        "It moves on 6 November.",
        "It moves on November 1, 2026.",
        "It moves on 16 October.",
        "It moves in November.",
    ],
)
def test_another_day_is_not_the_move_day(answer: str) -> None:
    """The note's other date, the old yard's closing, is not the answer."""
    assert not says_the_move_day(answer)
