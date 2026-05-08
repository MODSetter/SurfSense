"""Turn LangGraph astream_events into SSE strings via the handler modules."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.services.streaming.emitter import EmitterRegistry
from app.tasks.chat.streaming.graph_stream.result import StreamingResult
from app.tasks.chat.streaming.handlers.chain_end import iter_chain_end_frames
from app.tasks.chat.streaming.handlers.chat_model_stream import (
    iter_chat_model_stream_frames,
)
from app.tasks.chat.streaming.handlers.custom_event_dispatch import (
    iter_custom_event_frames,
)
from app.tasks.chat.streaming.handlers.tool_end import iter_tool_end_frames
from app.tasks.chat.streaming.handlers.tool_start import iter_tool_start_frames
from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.thinking_step_completion import (
    complete_active_thinking_step,
)


@dataclass
class EventRelayConfig:
    """Optional relay tuning (sub-agent tools, text suppression)."""

    subagent_entry_tool_names: frozenset[str] = field(
        default_factory=lambda: frozenset({"task"})
    )
    suppress_main_text_inside_tools: bool = True


class EventRelay:
    """Dispatches graph events to streaming handlers and optional emitters."""

    def __init__(
        self,
        *,
        streaming_service: Any,
        config: EventRelayConfig | None = None,
    ) -> None:
        self.streaming_service = streaming_service
        self.config = config or EventRelayConfig()
        reg = getattr(streaming_service, "emitter_registry", None)
        self.emitter_registry = reg if reg is not None else EmitterRegistry()

    async def relay(
        self,
        events: AsyncIterator[dict[str, Any]],
        *,
        state: AgentEventRelayState,
        result: StreamingResult,
        step_prefix: str = "thinking",
        content_builder: Any | None = None,
        config: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Yield SSE for each event from the async iterator, then finalize text/thinking."""
        graph_config = config or {}
        async for event in events:
            event_type = event.get("event", "")
            if event_type == "on_chat_model_stream":
                for frame in iter_chat_model_stream_frames(
                    event,
                    state=state,
                    streaming_service=self.streaming_service,
                    content_builder=content_builder,
                    step_prefix=step_prefix,
                ):
                    yield frame
            elif event_type == "on_tool_start":
                for frame in iter_tool_start_frames(
                    event,
                    state=state,
                    streaming_service=self.streaming_service,
                    content_builder=content_builder,
                    result=result,
                    step_prefix=step_prefix,
                ):
                    yield frame
            elif event_type == "on_tool_end":
                for frame in iter_tool_end_frames(
                    event,
                    state=state,
                    streaming_service=self.streaming_service,
                    content_builder=content_builder,
                    result=result,
                    step_prefix=step_prefix,
                    config=graph_config,
                ):
                    yield frame
            elif event_type == "on_custom_event":
                for frame in iter_custom_event_frames(
                    event,
                    state=state,
                    streaming_service=self.streaming_service,
                    content_builder=content_builder,
                ):
                    yield frame
            elif event_type in ("on_chain_end", "on_agent_end"):
                for frame in iter_chain_end_frames(
                    event,
                    state=state,
                    streaming_service=self.streaming_service,
                    content_builder=content_builder,
                ):
                    yield frame

        if state.current_text_id is not None:
            yield self.streaming_service.format_text_end(state.current_text_id)
            if content_builder is not None:
                content_builder.on_text_end(state.current_text_id)
            state.current_text_id = None

        completion_event, new_active = complete_active_thinking_step(
            state=state,
            streaming_service=self.streaming_service,
            content_builder=content_builder,
            last_active_step_id=state.last_active_step_id,
            last_active_step_title=state.last_active_step_title,
            last_active_step_items=state.last_active_step_items,
            completed_step_ids=state.completed_step_ids,
        )
        if completion_event:
            yield completion_event
        state.last_active_step_id = new_active
