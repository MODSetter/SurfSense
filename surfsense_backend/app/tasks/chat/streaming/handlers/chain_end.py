"""Close open text when a LangGraph chain or agent node finishes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.tasks.chat.streaming.relay.state import AgentEventRelayState


def iter_chain_end_frames(
    _event: dict[str, Any],
    *,
    state: AgentEventRelayState,
    streaming_service: Any,
    content_builder: Any | None,
) -> Iterator[str]:
    """Close the open text stream if one is open."""
    if state.current_text_id is not None:
        yield streaming_service.format_text_end(state.current_text_id)
        if content_builder is not None:
            content_builder.on_text_end(state.current_text_id)
        state.current_text_id = None
