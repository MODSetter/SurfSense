"""Run LangGraph event streams through ``EventRelay``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.tasks.chat.streaming.graph_stream.result import StreamingResult
from app.tasks.chat.streaming.relay.event_relay import EventRelay
from app.tasks.chat.streaming.relay.state import AgentEventRelayState


async def stream_output(
    *,
    agent: Any,
    config: dict[str, Any],
    input_data: Any,
    streaming_service: Any,
    result: StreamingResult,
    step_prefix: str = "thinking",
    initial_step_id: str | None = None,
    initial_step_title: str = "",
    initial_step_items: list[str] | None = None,
    content_builder: Any | None = None,
    runtime_context: Any = None,
) -> AsyncIterator[str]:
    """Yield SSE frames from agent ``astream_events`` via ``EventRelay``."""
    state = AgentEventRelayState.for_invocation(
        initial_step_id=initial_step_id,
        initial_step_title=initial_step_title,
        initial_step_items=initial_step_items,
    )

    astream_kwargs: dict[str, Any] = {"config": config, "version": "v2"}
    if runtime_context is not None:
        astream_kwargs["context"] = runtime_context

    events = agent.astream_events(input_data, **astream_kwargs)
    relay = EventRelay(streaming_service=streaming_service)
    async for frame in relay.relay(
        events,
        state=state,
        result=result,
        step_prefix=step_prefix,
        content_builder=content_builder,
        config=config,
    ):
        yield frame

    result.accumulated_text = state.accumulated_text
