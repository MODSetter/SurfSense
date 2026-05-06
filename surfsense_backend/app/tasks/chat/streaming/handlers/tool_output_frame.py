"""Emit tool-output SSE and optional assistant content updates."""

from __future__ import annotations

from typing import Any


def emit_tool_output_available_frame(
    *,
    streaming_service: Any,
    content_builder: Any | None,
    langchain_id_holder: dict[str, str | None],
    call_id: str,
    output: Any,
) -> str:
    if content_builder is not None:
        content_builder.on_tool_output_available(
            call_id, output, langchain_id_holder["value"]
        )
    return streaming_service.format_tool_output_available(
        call_id,
        output,
        langchain_tool_call_id=langchain_id_holder["value"],
    )
