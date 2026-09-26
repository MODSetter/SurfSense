"""How a turn's fixed parts, the answer, and history share one context window."""

import pytest

from modules.chat.budget import (
    ANSWER_RESERVE_TOKENS,
    DEFAULT_HISTORY_TOKENS,
    answer_max_tokens,
    history_budget,
)

pytestmark = pytest.mark.unit


def test_an_unknown_window_keeps_todays_fixed_budget() -> None:
    """A remote endpoint that reports no window is not a smaller window; it is
    an absent fact. Nothing here can tell the fixed parts fit, so the fallback
    is today's number rather than a guess that could be too generous."""
    assert history_budget(None) == DEFAULT_HISTORY_TOKENS


def test_a_known_window_leaves_less_room_the_smaller_it_is() -> None:
    """The whole point: history is spent out of what is actually left, not a
    constant that assumes a 16384 window it may not have."""
    narrow = history_budget(8192)
    wide = history_budget(16384)

    assert 0 <= narrow < wide


def test_the_fixed_parts_and_the_answer_never_starve_a_tight_window() -> None:
    """A window smaller than the fixed parts plus the reserve leaves zero for
    history rather than a negative number that would corrupt a slice."""
    assert history_budget(1) == 0


def test_the_answer_reserve_is_capped_only_when_the_window_is_known() -> None:
    """Sending a fixed cap to an endpoint whose real window might be far
    larger would truncate replies for a limit that does not apply there."""
    assert answer_max_tokens(None) is None
    assert answer_max_tokens(16384) == ANSWER_RESERVE_TOKENS
