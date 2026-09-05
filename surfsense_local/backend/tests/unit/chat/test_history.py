"""Sliding window: the system and new turn are pinned, oldest history is dropped."""

import pytest

from modules.chat.history import HISTORY_BUDGET_TOKENS, build_messages
from modules.chat.models import ChatMessage, MessageRole

pytestmark = pytest.mark.unit


def _turn(marker: str, tokens: int) -> ChatMessage:
    # Four characters per estimated token, matching the trimmer's heuristic.
    return ChatMessage(
        role=MessageRole.USER, content={"text": marker * (tokens * 4)}
    )


def test_the_system_and_new_turn_bracket_the_history() -> None:
    """Whatever the window keeps, the system leads and the new user turn trails."""
    messages = build_messages("SYSTEM", [_turn("a", 10)], "ask")

    assert messages[0].role == "system"
    assert messages[0].content == "SYSTEM"
    assert messages[-1].role == "user"
    assert messages[-1].content == "ask"


def test_the_oldest_turns_over_budget_are_dropped() -> None:
    """Turns are kept newest-first until the budget is spent, in original order."""
    half = HISTORY_BUDGET_TOKENS // 2
    history = [_turn("x", half), _turn("y", half), _turn("z", half)]

    kept = build_messages("SYSTEM", history, "ask")[1:-1]

    # Three half-budget turns cannot all fit; the oldest falls away, order holds.
    assert [message.content[0] for message in kept] == ["y", "z"]
