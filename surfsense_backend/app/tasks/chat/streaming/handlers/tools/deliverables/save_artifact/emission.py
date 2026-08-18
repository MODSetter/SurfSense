"""save_artifact: artifact card payload and terminal line."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    output = ctx.tool_output
    if isinstance(output, dict) and output.get("status") == "saved":
        yield ctx.emit_tool_output_card(output)
        yield ctx.streaming_service.format_terminal_info(
            f"Artifact saved: {output.get('title', 'Document')}",
            "success",
        )
        return
    error = (
        output.get("error", "Unknown error")
        if isinstance(output, dict)
        else "Unknown error"
    )
    yield ctx.streaming_service.format_terminal_info(
        f"Artifact save failed: {error}",
        "error",
    )
