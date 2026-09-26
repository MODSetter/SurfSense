"""Sliding window: the system and new turn are pinned, oldest history is dropped."""

import pytest

from modules.chat.budget import DEFAULT_HISTORY_TOKENS
from modules.chat.history import build_messages
from modules.chat.models import ChatMessage, MessageRole

pytestmark = pytest.mark.unit


def _turn(marker: str, tokens: int) -> ChatMessage:
    # Four characters per estimated token, matching the trimmer's heuristic.
    return ChatMessage(
        role=MessageRole.USER, content={"text": marker * (tokens * 4)}
    )


async def test_the_system_and_new_turn_bracket_the_history() -> None:
    """Whatever the window keeps, the system leads and the new user turn trails."""
    messages = await build_messages("SYSTEM", [_turn("a", 10)], "ask")

    assert messages[0].role == "system"
    assert messages[0].content == "SYSTEM"
    assert messages[-1].role == "user"
    assert messages[-1].content == "ask"


async def test_the_oldest_turns_over_budget_are_dropped() -> None:
    """Turns are kept newest-first until the budget is spent, in original order."""
    half = DEFAULT_HISTORY_TOKENS // 2
    history = [_turn("x", half), _turn("y", half), _turn("z", half)]

    kept = (await build_messages("SYSTEM", history, "ask"))[1:-1]

    # Three half-budget turns cannot all fit; the oldest falls away, order holds.
    assert [message.content[0] for message in kept] == ["y", "z"]


async def test_a_caller_supplied_budget_overrides_the_default() -> None:
    """A model with a known, narrower window keeps less history than the
    default figure would allow, without waiting for the default to change."""
    history = [_turn("a", 50), _turn("b", 50)]

    kept_default = (await build_messages("SYSTEM", history, "ask"))[1:-1]
    kept_tight = (
        await build_messages("SYSTEM", history, "ask", history_budget=50)
    )[1:-1]

    assert len(kept_tight) < len(kept_default)


async def test_an_exact_counter_is_preferred_over_the_heuristic() -> None:
    """The whole point of wiring a counter through: a turn the heuristic would
    keep because it under-counted a dense, short string is trimmed correctly
    once the model's own tokenizer prices it."""
    # Four characters, which the heuristic prices at 1 token; the fake
    # tokenizer says this string is actually 40, well over a 10 token budget.
    history = [_turn("q", 1)]

    async def exact(text: str) -> int:
        return 40

    kept = (
        await build_messages("SYSTEM", history, "ask", history_budget=10, token_count=exact)
    )[1:-1]

    assert kept == []


async def test_a_counter_that_fails_falls_back_to_the_heuristic_for_that_turn() -> None:
    """None is a real answer (no endpoint, a transient failure), not a zero:
    the turn is still priced, just approximately, rather than being kept for
    free or dropped as though it cost nothing."""
    history = [_turn("q", DEFAULT_HISTORY_TOKENS)]

    async def unavailable(text: str) -> int | None:
        return None

    kept = (
        await build_messages(
            "SYSTEM", history, "ask", history_budget=10, token_count=unavailable
        )
    )[1:-1]

    # The heuristic prices this turn at DEFAULT_HISTORY_TOKENS, over a budget
    # of 10, so it is still dropped: the fallback ran, not a free pass.
    assert kept == []
