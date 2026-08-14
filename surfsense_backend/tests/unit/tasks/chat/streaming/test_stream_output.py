"""Tests for ``stream_output`` (LangGraph events → SSE)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.tasks.chat.content_builder import AssistantContentBuilder
from app.tasks.chat.streaming.graph_stream import stream_output
from app.tasks.chat.streaming.graph_stream.result import StreamingResult
from app.tasks.chat.streaming.handlers.chat_model_stream import (
    iter_chat_model_stream_frames,
)
from app.tasks.chat.streaming.relay.state import AgentEventRelayState

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

    def generate_reasoning_id(self) -> str:
        return "reasoning-1"

    def format_reasoning_start(self, reasoning_id: str) -> str:
        return f"reasoning_start:{reasoning_id}"

    def format_reasoning_delta(self, reasoning_id: str, text: str) -> str:
        return f"reasoning_delta:{reasoning_id}:{text}"

    def format_reasoning_end(self, reasoning_id: str) -> str:
        return f"reasoning_end:{reasoning_id}"

    def format_tool_input_start(
        self,
        tool_call_id: str,
        tool_name: str,
        **_: Any,
    ) -> str:
        return f"tool_start:{tool_call_id}:{tool_name}"

    def format_tool_input_delta(self, tool_call_id: str, args: str) -> str:
        return f"tool_delta:{tool_call_id}:{args}"


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


async def test_stream_output_emits_text_lifecycle_and_updates_result() -> None:
    service = _StreamingService()
    agent = _Agent(
        [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _Chunk(content="Hello")},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": _Chunk(content=" world")},
            },
        ]
    )
    result = StreamingResult()

    frames = await _collect(
        stream_output(
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


async def test_stream_output_passes_runtime_context_to_agent() -> None:
    service = _StreamingService()

    class _ContextAwareAgent:
        async def astream_events(self, input_data: Any, **kwargs: Any):
            del input_data
            text = "ctx-ok" if kwargs.get("context") else "ctx-missing"
            yield {"event": "on_chat_model_stream", "data": {"chunk": _Chunk(text)}}

    agent = _ContextAwareAgent()
    result = StreamingResult()

    frames = await _collect(
        stream_output(
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


def test_one_provider_chunk_preserves_interleaved_part_order() -> None:
    builder = AssistantContentBuilder()
    frames = list(
        iter_chat_model_stream_frames(
            {
                "data": {
                    "chunk": _Chunk(
                        content=[
                            {"type": "reasoning", "reasoning": "think one"},
                            {"type": "text", "text": "answer one"},
                            {"type": "reasoning", "reasoning": "think two"},
                            {
                                "type": "tool_call_chunk",
                                "index": 0,
                                "id": "call-search",
                                "name": "google_search_scrape",
                                "args": '{"query":"x"}',
                            },
                            {"type": "text", "text": "answer two"},
                        ]
                    )
                }
            },
            state=AgentEventRelayState(),
            streaming_service=_StreamingService(),
            content_builder=builder,
            step_prefix="turn",
        )
    )

    assert frames == [
        "reasoning_start:reasoning-1",
        "reasoning_delta:reasoning-1:think one",
        "reasoning_end:reasoning-1",
        "text_start:text-1",
        "text_delta:text-1:answer one",
        "text_end:text-1",
        "reasoning_start:reasoning-1",
        "reasoning_delta:reasoning-1:think two",
        "reasoning_end:reasoning-1",
        "tool_start:call-search:google_search_scrape",
        'tool_delta:call-search:{"query":"x"}',
        "text_start:text-2",
        "text_delta:text-2:answer two",
    ]
    assert [part["type"] for part in builder.snapshot()] == [
        "reasoning",
        "text",
        "reasoning",
        "tool-call",
        "text",
    ]
    assert [part.get("text") for part in builder.snapshot()] == [
        "think one",
        "answer one",
        "think two",
        None,
        "answer two",
    ]


def test_reasoning_content_precedes_visible_string_from_same_chunk() -> None:
    frames = list(
        iter_chat_model_stream_frames(
            {
                "data": {
                    "chunk": _Chunk(
                        content="visible answer",
                        additional_kwargs={"reasoning_content": "private reasoning"},
                    )
                }
            },
            state=AgentEventRelayState(),
            streaming_service=_StreamingService(),
            content_builder=AssistantContentBuilder(),
            step_prefix="turn",
        )
    )

    assert frames == [
        "reasoning_start:reasoning-1",
        "reasoning_delta:reasoning-1:private reasoning",
        "reasoning_end:reasoning-1",
        "text_start:text-1",
        "text_delta:text-1:visible answer",
    ]
