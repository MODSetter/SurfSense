"""A Claude Code transcript read back as the thread's turns, as an opencode session is."""

from typing import Any

import pytest

from modules.agent.agent_threads.replies import thread_turns
from modules.agent.engines.claude_code.transcript_shape import opencode_messages

pytestmark = pytest.mark.unit


def _user(uuid: str, content: Any, **extra: Any) -> dict[str, Any]:
    return {
        "type": "user",
        "uuid": uuid,
        "timestamp": "2026-10-16T10:00:00.000Z",
        "isSidechain": False,
        "message": {"role": "user", "content": content},
        **extra,
    }


def _assistant(message_id: str, block: dict[str, Any], at: str) -> dict[str, Any]:
    return {
        "type": "assistant",
        "uuid": f"{message_id}-{block['type']}",
        "timestamp": at,
        "isSidechain": False,
        "message": {"id": message_id, "role": "assistant", "content": [block]},
    }


TURN = [
    {"type": "queue-operation", "timestamp": "2026-10-16T10:00:00.000Z"},
    _user(
        "turn-1",
        [
            {"type": "text", "text": "[surfsense-scope: 4]\nUse only that one."},
            {"type": "text", "text": "What grew in Q3?"},
        ],
    ),
    {"type": "attachment", "uuid": "a1", "timestamp": "2026-10-16T10:00:00.000Z"},
    _assistant(
        "msg_1",
        {"type": "thinking", "thinking": "Search first.", "signature": "s"},
        "2026-10-16T10:00:01.000Z",
    ),
    _assistant(
        "msg_1",
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "mcp__surfsense__search_sources",
            "input": {"query": "Q3"},
        },
        "2026-10-16T10:00:02.000Z",
    ),
    _user(
        "result-1",
        [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": [{"type": "text", "text": "[1] Revenue grew 12%."}],
            }
        ],
    ),
    _assistant(
        "msg_2",
        {"type": "text", "text": "Revenue grew 12%."},
        "2026-10-16T10:00:04.000Z",
    ),
]


def test_a_turn_is_the_users_words_then_one_reply_with_its_steps() -> None:
    """Thinking, a call and its result, and the answer, across two API messages."""
    turns = thread_turns(opencode_messages(TURN), [])

    assert [turn["role"] for turn in turns] == ["user", "assistant"]
    user, reply = turns
    assert user["id"] == "turn-1"
    # SurfSense's notes travel as blocks before the user's own words.
    assert user["content"]["text"] == "What grew in Q3?"
    assert user["content"]["scope"] is not None
    assert reply["id"] == "turn-1:reply"
    assert reply["content"]["text"] == "Revenue grew 12%."
    (step,) = reply["content"]["steps"]
    assert step["tool"] == "surfsense_search_sources"
    assert step["status"] == "completed"
    assert step["output"] == "[1] Revenue grew 12%."
    assert reply["created_at"] == "2026-10-16T10:00:01Z"
    assert reply["completed_at"] == "2026-10-16T10:00:04Z"


def test_claude_codes_own_messages_are_not_turns() -> None:
    """A compaction's summary, a meta message and an interruption notice are Claude Code's."""
    entries = [
        *TURN,
        {"type": "system", "subtype": "compact_boundary", "uuid": "c1"},
        _user("summary", "This session is being continued…", isCompactSummary=True),
        _user("meta", "Caveat: the messages below…", isMeta=True),
        _user("stop", [{"type": "text", "text": "[Request interrupted by user]"}]),
        _user("turn-2", "And Q4?"),
        _assistant(
            "msg_3",
            {"type": "text", "text": "Not yet known."},
            "2026-10-16T10:01:00.000Z",
        ),
    ]

    turns = thread_turns(opencode_messages(entries), [])

    assert [turn["id"] for turn in turns] == [
        "turn-1",
        "turn-1:reply",
        "turn-2",
        "turn-2:reply",
    ]


def test_a_subagents_entries_are_left_out() -> None:
    """SurfSense gives Claude Code no subagents; a sidechain is never the thread's."""
    sidechain = {**_user("side", "hidden"), "isSidechain": True}

    turns = thread_turns(opencode_messages([*TURN, sidechain]), [])

    assert len(turns) == 2
