"""Behavior tests for orchestrator ``stream_chat`` public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.tasks.chat.streaming.orchestration import StreamExecutionInput
from app.tasks.chat.streaming.orchestration.orchestrator import stream_chat

pytestmark = pytest.mark.unit


@dataclass
class _Chunk:
    content: Any = ""
    additional_kwargs: dict[str, Any] = field(default_factory=dict)
    tool_call_chunks: list[dict[str, Any]] = field(default_factory=list)


class _StreamingService:
    def __init__(self) -> None:
        self._text_idx = 0

    def generate_text_id(self) -> str:
        self._text_idx += 1
        return f"text-{self._text_idx}"

    def format_text_start(self, text_id: str) -> str:
        return f"text_start:{text_id}"

    def format_text_delta(self, text_id: str, text: str) -> str:
        return f"text_delta:{text_id}:{text}"

    def format_text_end(self, text_id: str) -> str:
        return f"text_end:{text_id}"


class _Agent:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = list(events)
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    async def astream_events(self, input_data: Any, **kwargs: Any):
        self.calls.append((input_data, kwargs))
        for event in self.events:
            yield event


async def _collect(stream: Any) -> list[str]:
    out: list[str] = []
    async for x in stream:
        out.append(x)
    return out


async def test_stream_chat_uses_orchestration_input_path() -> None:
    service = _StreamingService()
    agent = _Agent(
        [
            {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(content="hello")}},
            {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(content="!")}},
        ]
    )
    frames = await _collect(
        stream_chat(
            user_query="ignored-here",
            search_space_id=1,
            chat_id=77,
            orchestration_input=StreamExecutionInput(
                agent=agent,
                config={"configurable": {"thread_id": "thread-1"}},
                input_data={"messages": []},
                streaming_service=service,
            ),
        )
    )

    assert frames == [
        "text_start:text-1",
        "text_delta:text-1:hello",
        "text_delta:text-1:!",
        "text_end:text-1",
    ]
    assert agent.calls
    assert agent.calls[0][1]["version"] == "v2"
