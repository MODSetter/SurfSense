"""What a thread's session tells the next turn: its last exchange, and the tools it used."""

import pytest

from modules.agent.tool_exposure.thread_history import asked_of

pytestmark = pytest.mark.unit


def _user(text: str) -> dict:
    return {"id": f"u-{text}", "type": "user", "text": text}


def _step(*items: dict) -> dict:
    return {"id": "a", "type": "assistant", "content": list(items)}


def _call(name: str) -> dict:
    return {"type": "tool", "id": "c", "name": name, "state": {"status": "completed"}}


def test_the_last_exchange_is_searched_with_the_new_message() -> None:
    """It fixed follow-ups such as "now the other one"."""
    messages = [
        _user("open the Q3 issues in Linear"),
        _step({"type": "text", "text": "Here are 4 issues."}),
        {"id": "i", "type": "idle", "outcome": "succeeded"},
    ]

    asked = asked_of(messages, "now the other one", frozenset())

    assert asked.message == "now the other one"
    assert "Q3 issues in Linear" in asked.previous
    assert "Here are 4 issues." in asked.previous


def test_tools_used_since_the_last_compaction_stay_held() -> None:
    """Calls before the last compaction are forgotten, as the model forgot them."""
    messages = [
        _user("first"),
        _step(_call("linear_list_issues")),
        {"id": "c", "type": "compaction", "status": "completed", "summary": "..."},
        _user("second"),
        _step(_call("gcal_list_events"), _call("read")),
    ]

    asked = asked_of(messages, "third", frozenset({"notes"}))

    assert asked.used == frozenset({"gcal_list_events", "read"})
    assert asked.mentioned == frozenset({"notes"})


def test_a_new_thread_asks_with_its_message_alone() -> None:
    """No turn before it, and no tools used."""
    asked = asked_of([], "hello", frozenset())

    assert (asked.previous, asked.used) == ("", frozenset())
