"""
Integration test harness for the SurfSense agent stack.

The plan calls for an ``LLMToolEmulator``-backed harness for end-to-end
replay of ``stream_new_chat``. The currently-installed langchain version
does not expose ``LLMToolEmulator``, so this harness builds the equivalent
on top of :class:`langchain_core.language_models.fake_chat_models.FakeMessagesListChatModel`.

The harness lets a test author script a sequence of model responses
(text + optional tool calls) and replay them against the new_chat agent
graph. Tools are stubbed via ``StubToolSpec`` -> ``langchain_core.tools.tool``
decorator and execute deterministic Python callbacks.

Used by:
- ``tests/integration/agents/new_chat/test_feature_flag_smoke.py`` to
  confirm the kill-switch path produces identical-shape output regardless
  of which middleware flags are toggled.
- Future per-tier PRs to record golden transcripts.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, tool


class _ToolBindingFakeChatModel(FakeMessagesListChatModel):
    """Adapter so the harness model can pretend it understands ``bind_tools``.

    The base ``FakeMessagesListChatModel`` raises ``NotImplementedError`` from
    ``bind_tools``, but ``langchain.agents.create_agent`` always calls
    ``bind_tools`` to attach the tool registry. We don't actually need the
    fake to honor the tool schema — it's already scripted to emit the right
    tool calls — so we return self.
    """

    def bind_tools(  # type: ignore[override]
        self,
        tools: Sequence[Any],
        *,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self


@dataclass
class StubToolSpec:
    """A test-mode tool: a name, description, and a deterministic body."""

    name: str
    description: str
    handler: Callable[..., Any]
    args_schema: dict[str, Any] | None = None

    def build(self) -> BaseTool:
        """Realize as a `langchain_core.tools.BaseTool`."""

        @tool(name_or_callable=self.name, description=self.description)
        def _stub_tool(**kwargs: Any) -> Any:
            return self.handler(**kwargs)

        return _stub_tool


@dataclass
class ScriptedTurn:
    """One scripted assistant turn.

    `text` is the assistant text (may be empty if pure tool call).
    `tool_calls` is a list of dicts ``{name, args, id}``; if non-empty, the
    agent will route to those tools and append a follow-up turn.
    """

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def build_scripted_messages(turns: list[ScriptedTurn]) -> list[BaseMessage]:
    """Convert :class:`ScriptedTurn` records to AIMessage payloads."""
    out: list[BaseMessage] = []
    for turn in turns:
        tool_calls: list[dict[str, Any]] = []
        for tc in turn.tool_calls:
            tool_calls.append(
                {
                    "name": tc["name"],
                    "args": tc.get("args", {}),
                    "id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                }
            )
        out.append(AIMessage(content=turn.text, tool_calls=tool_calls or []))
    return out


@dataclass
class ScriptedHarness:
    """Bundle of (model, tools) ready to plug into ``create_agent``."""

    model: _ToolBindingFakeChatModel
    tools: list[BaseTool]


def build_scripted_harness(
    *,
    turns: list[ScriptedTurn],
    tools: list[StubToolSpec] | None = None,
    sleep: float | None = None,
) -> ScriptedHarness:
    """Construct a deterministic agent harness from a script.

    Example::

        harness = build_scripted_harness(
            turns=[
                ScriptedTurn(tool_calls=[{"name": "echo", "args": {"x": 1}}]),
                ScriptedTurn(text="done"),
            ],
            tools=[
                StubToolSpec(name="echo", description="echo args", handler=lambda **kw: kw),
            ],
        )
    """
    messages = build_scripted_messages(turns)
    model = _ToolBindingFakeChatModel(responses=messages, sleep=sleep)
    realized_tools = [t.build() for t in (tools or [])]
    return ScriptedHarness(model=model, tools=realized_tools)


__all__ = [
    "ScriptedHarness",
    "ScriptedTurn",
    "StubToolSpec",
    "build_scripted_harness",
    "build_scripted_messages",
]
