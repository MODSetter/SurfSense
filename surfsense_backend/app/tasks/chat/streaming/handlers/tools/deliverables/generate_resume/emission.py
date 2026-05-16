"""generate_resume: full payload + terminal line."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    payload = out if isinstance(out, dict) else {"result": out}
    yield ctx.emit_tool_output_card(payload)
    if isinstance(out, dict) and out.get("status") == "ready":
        yield ctx.streaming_service.format_terminal_info(
            f"Resume generated: {out.get('title', 'Resume')}",
            "success",
        )
    else:
        error_msg = (
            out.get("error", "Unknown error")
            if isinstance(out, dict)
            else "Unknown error"
        )
        yield ctx.streaming_service.format_terminal_info(
            f"Resume generation failed: {error_msg}",
            "error",
        )
