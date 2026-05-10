"""Default tool-output card and a short completion terminal line."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    yield ctx.emit_tool_output_card(
        {
            "status": "completed",
            "result_length": len(str(ctx.tool_output)),
        },
    )
    yield ctx.streaming_service.format_terminal_info(
        f"Tool {ctx.tool_name} completed",
        "success",
    )
