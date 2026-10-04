"""How a turn's fixed parts, the answer, and history share one context window."""

import pytest
from pydantic import ValidationError

from modules.chat.budget import (
    ANSWER_RESERVE_TOKENS,
    CHARS_PER_TOKEN,
    DEFAULT_HISTORY_TOKENS,
    QUESTION_CHARS,
    QUESTION_TOKENS,
    SMALLEST_IMAGE_TOKENS,
    answer_max_tokens,
    history_budget,
    image_room,
)
from modules.chat.schemas import MessageCreate

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


def test_the_question_cannot_exceed_its_share() -> None:
    """The question's 1,024 tokens are a cap the wire enforces, not a share it
    hopes for: priced by the same characters-per-token estimate history uses,
    a longer message is refused before any model or retrieval is touched."""
    assert QUESTION_CHARS // CHARS_PER_TOKEN == QUESTION_TOKENS
    MessageCreate(text="x" * QUESTION_CHARS)
    MessageCreate(text="x" * QUESTION_CHARS + "   ")  # whitespace is stripped first
    with pytest.raises(ValidationError):
        MessageCreate(text="x" * (QUESTION_CHARS + 1))


def test_image_room_is_unknown_without_a_window() -> None:
    """A remote endpoint that reports no window is never refused on its images."""
    assert image_room(None, 0) is None


def test_three_images_fit_an_8192_window_at_the_cheapest_projector() -> None:
    """Gemma 3 spends 256 per image: three cost 768, which a floor window holds."""
    assert image_room(8192, len("what are these?")) >= 3


def test_image_room_is_a_lower_bound_not_the_history_price() -> None:
    """Only the reserve and the turn's own text are taken: a refusal must be sure."""
    assert (
        image_room(2048, 0) == (2048 - ANSWER_RESERVE_TOKENS) // SMALLEST_IMAGE_TOKENS
    )


def test_the_turns_own_text_takes_room_from_its_images() -> None:
    """Long excerpts leave fewer images room."""
    excerpts = 400 * CHARS_PER_TOKEN

    assert image_room(2048, excerpts) < image_room(2048, 0)


def test_a_window_smaller_than_the_reserve_has_no_room() -> None:
    """Floors at zero rather than going negative."""
    assert image_room(512, 0) == 0
