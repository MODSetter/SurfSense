"""Behavior tests for orchestration event-stream execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.tasks.chat.streaming.orchestration import stream_agent_events
from app.tasks.chat.streaming.orchestration.output import StreamOutput

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


async def test_stream_agent_events_emits_text_lifecycle_and_updates_result() -> None:
    service = _StreamingService()
    agent = _Agent(
        [
            {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(content="Hello")}},
            {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(content=" world")}},
        ]
    )
    result = StreamOutput()

    frames = await _collect(
        stream_agent_events(
            agent=agent,
            config={"configurable": {"thread_id": "t-1"}},
            input_data={"messages": []},
            streaming_service=service,
            result=result,
        )
    )

    assert frames == [
        "text_start:text-1",
        "text_delta:text-1:Hello",
        "text_delta:text-1: world",
        "text_end:text-1",
    ]
    assert result.accumulated_text == "Hello world"
    assert result.agent_called_update_memory is False


async def test_stream_agent_events_passes_runtime_context_to_agent() -> None:
    service = _StreamingService()
    class _ContextAwareAgent:
        async def astream_events(self, input_data: Any, **kwargs: Any):
            del input_data
            text = "ctx-ok" if kwargs.get("context") else "ctx-missing"
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(text)}}

    agent = _ContextAwareAgent()
    result = StreamOutput()

    frames = await _collect(
        stream_agent_events(
            agent=agent,
            config={"configurable": {"thread_id": "t-2"}},
            input_data={"messages": []},
            streaming_service=service,
            result=result,
            runtime_context={"mentioned_document_ids": [1, 2]},
        )
    )

    assert frames == [
        "text_start:text-1",
        "text_delta:text-1:ctx-ok",
        "text_end:text-1",
    ]
