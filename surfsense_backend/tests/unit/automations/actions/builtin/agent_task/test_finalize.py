"""Lock ``extract_final_assistant_message`` — what surfaces in run output.

Each scenario is one shape the agent runtime is observed to produce.
Locking these means we can refactor the extractor without losing
backwards compatibility with already-stored ``run.output`` payloads.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.automations.actions.builtin.agent_task.finalize import (
    extract_final_assistant_message,
)

pytestmark = pytest.mark.unit


def test_extract_returns_last_ai_message_string_content() -> None:
    """The canonical shape: the agent's final ``AIMessage`` carries a
    plain string. That string is returned verbatim, trimmed."""
    result = {
        "messages": [
            HumanMessage(content="ask"),
            AIMessage(content="the answer"),
        ]
    }

    assert extract_final_assistant_message(result) == "the answer"


def test_extract_concatenates_text_parts_and_skips_non_text_parts() -> None:
    """Multi-part AIMessage content (Anthropic / OpenAI list shape) joins
    its ``text`` parts in order; non-text parts (tool_use, images, ...)
    are skipped. Locks the wire shape used when the model emits tool
    calls alongside narrative text in the same turn."""
    result = {
        "messages": [
            AIMessage(
                content=[
                    {"type": "text", "text": "Hello "},
                    {"type": "tool_use", "name": "search", "input": {}},
                    {"type": "text", "text": "world"},
                ]
            )
        ]
    }

    assert extract_final_assistant_message(result) == "Hello world"


def test_extract_returns_last_ai_message_skipping_tool_messages() -> None:
    """When the transcript ends with tool calls and tool results, the
    extractor still walks back to the **last** ``AIMessage`` (the agent's
    final narrative answer). Locks resilience against trailing
    ``ToolMessage`` payloads in the transcript."""
    result = {
        "messages": [
            HumanMessage(content="ask"),
            AIMessage(content="thinking..."),
            ToolMessage(content="tool output", tool_call_id="tc-1"),
            AIMessage(content="final answer"),
            ToolMessage(content="trailing tool noise", tool_call_id="tc-2"),
        ]
    }

    assert extract_final_assistant_message(result) == "final answer"


def test_extract_returns_none_when_no_assistant_text_is_present() -> None:
    """No ``AIMessage`` with extractable text → ``None`` rather than the
    empty string. Lets callers branch on "did the agent actually say
    anything?" rather than guess whether ``""`` means silence or empty
    output. Empty-string contents are normalized to ``None`` too."""
    no_ai = {"messages": [HumanMessage(content="just a question")]}
    only_tools = {
        "messages": [
            AIMessage(content=[{"type": "tool_use", "name": "x", "input": {}}])
        ]
    }
    empty_string = {"messages": [AIMessage(content="   ")]}

    assert extract_final_assistant_message(no_ai) is None
    assert extract_final_assistant_message(only_tools) is None
    assert extract_final_assistant_message(empty_string) is None
