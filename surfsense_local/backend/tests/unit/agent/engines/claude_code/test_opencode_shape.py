"""A Claude Code turn reaches the thread as the frames an opencode turn sends."""

from typing import Any

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from modules.agent.agent_threads.replies import turn_reply
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.engines.claude_code.opencode_shape import OpencodeShape

pytestmark = pytest.mark.unit
SESSION = "claude-session"


def _stream(event: dict[str, Any]) -> StreamEvent:
    return StreamEvent(uuid="u", session_id=SESSION, event=event)


def _start(message_id: str) -> StreamEvent:
    return _stream({"type": "message_start", "message": {"id": message_id}})


def _block(index: int, block: dict[str, Any]) -> StreamEvent:
    return _stream(
        {"type": "content_block_start", "index": index, "content_block": block}
    )


def _delta(index: int, delta: dict[str, Any]) -> StreamEvent:
    return _stream({"type": "content_block_delta", "index": index, "delta": delta})


def _stop(index: int) -> StreamEvent:
    return _stream({"type": "content_block_stop", "index": index})


def _assistant(message_id: str, *blocks: Any) -> AssistantMessage:
    return AssistantMessage(content=list(blocks), model="sonnet", message_id=message_id)


def _done() -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id=SESSION,
    )


def _frames(*messages: Any) -> tuple[list[dict[str, Any]], TurnFrames]:
    shape = OpencodeShape(SESSION)
    turn = TurnFrames(SESSION)
    frames = []
    for event in shape.user("turn-1", created_ms=1_000):
        frames += turn.frames(event)
    for message in messages:
        for event in shape.read(message):
            frames += turn.frames(event)
    return frames, turn


def test_streamed_text_is_the_reply_and_the_turn_ends() -> None:
    """The reply streams as it is written, and the result ends the turn."""
    frames, turn = _frames(
        _start("msg_1"),
        _block(0, {"type": "text", "text": ""}),
        _delta(0, {"type": "text_delta", "text": "Revenue "}),
        _delta(0, {"type": "text_delta", "text": "grew 12%."}),
        _stop(0),
        _assistant("msg_1", TextBlock("Revenue grew 12%.")),
        _done(),
    )

    assert frames[0]["type"] == "accepted"
    assert frames[0]["user_message_id"] == "turn-1"
    assert [f["text"] for f in frames if f["type"] == "delta"] == [
        "Revenue ",
        "grew 12%.",
    ]
    assert turn.finished


def test_text_that_never_streamed_still_reaches_the_reply() -> None:
    """Claude Code may send a block whole; nothing of the reply is lost."""
    frames, _ = _frames(
        _assistant("msg_1", TextBlock("Done.")),
        _done(),
    )

    assert [f["text"] for f in frames if f["type"] == "delta"] == ["Done."]


def test_thinking_is_reasoning_and_says_when_it_ended() -> None:
    """The thread shows how long the model thought, once."""
    frames, _ = _frames(
        _start("msg_1"),
        _block(0, {"type": "thinking", "thinking": ""}),
        _delta(0, {"type": "thinking_delta", "thinking": "Check Q3 first."}),
        _stop(0),
        _assistant("msg_1", ThinkingBlock("Check Q3 first.", "sig")),
        _done(),
    )

    assert [f["text"] for f in frames if f["type"] == "reasoning"] == [
        "Check Q3 first."
    ]
    assert [f["type"] for f in frames].count("reasoning-end") == 1


def test_a_tool_call_is_a_step_named_and_shown_as_opencodes() -> None:
    """Running with its input, then completed with what it returned."""
    frames, _ = _frames(
        _start("msg_1"),
        _block(0, {"type": "tool_use", "id": "toolu_1", "name": "Read", "input": {}}),
        _stop(0),
        _assistant(
            "msg_1",
            ToolUseBlock("toolu_1", "Read", {"file_path": "sources/q3.txt"}),
        ),
        UserMessage(
            content=[ToolResultBlock("toolu_1", "Q3 revenue: 12%", is_error=False)]
        ),
        _done(),
    )

    steps = [f for f in frames if f["type"] == "agent-step"]
    assert [s["status"] for s in steps] == ["pending", "running", "completed"]
    assert steps[-1]["tool"] == "read"
    assert steps[-1]["call_id"] == "toolu_1"
    assert steps[-1]["input"] == {"path": "sources/q3.txt"}
    assert steps[-1]["output"] == "Q3 revenue: 12%"


def test_a_surfsense_tool_returns_its_text_and_a_refusal_is_an_error_step() -> None:
    """An MCP result's text blocks are the output; a refused call fails its step."""
    frames, _ = _frames(
        _assistant(
            "msg_1",
            ToolUseBlock("toolu_1", "mcp__surfsense__search_sources", {"query": "q3"}),
            ToolUseBlock("toolu_2", "Bash", {"command": "ls"}),
        ),
        UserMessage(
            content=[
                ToolResultBlock(
                    "toolu_1", [{"type": "text", "text": "Found 2 passages."}]
                ),
                ToolResultBlock("toolu_2", "Bash is not available.", is_error=True),
            ]
        ),
        _done(),
    )

    ended = {
        s["tool"]: s
        for s in frames
        if s["type"] == "agent-step" and s["status"] in {"completed", "error"}
    }
    assert ended["surfsense_search_sources"]["output"] == "Found 2 passages."
    assert ended["bash"]["status"] == "error"
    assert ended["bash"]["error"] == "Bash is not available."


def test_words_after_a_tool_open_a_new_paragraph() -> None:
    """Each API message is one step's words, as opencode's parts are."""
    frames, _ = _frames(
        _assistant("msg_1", TextBlock("Let me check.")),
        _assistant("msg_1", ToolUseBlock("toolu_1", "Glob", {"pattern": "*.md"})),
        UserMessage(content=[ToolResultBlock("toolu_1", "a.md")]),
        _assistant("msg_2", TextBlock("Found a.md.")),
        _done(),
    )

    assert "".join(f["text"] for f in frames if f["type"] == "delta") == (
        "Let me check.\n\nFound a.md."
    )


def test_the_turn_read_live_is_the_reply_it_stores() -> None:
    """The reply is stated from what streamed: the transcript lands in batches, after."""
    shape = OpencodeShape(SESSION)
    shape.user("turn-1", created_ms=1_000)
    for message in [
        _assistant("msg_1", ToolUseBlock("toolu_1", "Glob", {"pattern": "*.md"})),
        UserMessage(content=[ToolResultBlock("toolu_1", "a.md")]),
        _assistant("msg_2", TextBlock("Found a.md.")),
        _done(),
    ]:
        shape.read(message)

    reply = turn_reply(shape.messages(), "turn-1", [])

    assert reply is not None
    assert reply["id"] == "turn-1:reply"
    assert reply["content"]["text"] == "Found a.md."
    assert [step["status"] for step in reply["content"]["steps"]] == ["completed"]
    assert reply["completed_at"] is not None
