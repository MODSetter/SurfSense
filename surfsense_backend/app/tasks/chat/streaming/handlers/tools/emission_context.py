"""Context for one tool-completion emission pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.tasks.chat.streaming.handlers.tool_output_frame import (
    emit_tool_output_available_frame,
)


@dataclass
class ToolCompletionEmissionContext:
    """Streaming service, tool output, and ids for completion frames."""

    tool_name: str
    tool_call_id: str
    tool_output: Any
    streaming_service: Any
    content_builder: Any | None
    langchain_tool_call_id_holder: dict[str, str | None]
    stream_result: Any
    langgraph_config: dict[str, Any]
    staged_workspace_file_path: str | None

    def emit_tool_output_card(self, payload: Any) -> str:
        return emit_tool_output_available_frame(
            streaming_service=self.streaming_service,
            content_builder=self.content_builder,
            langchain_id_holder=self.langchain_tool_call_id_holder,
            call_id=self.tool_call_id,
            output=payload,
        )
