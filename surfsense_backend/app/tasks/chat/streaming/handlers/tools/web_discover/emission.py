"""web_discover: ranked-hits card + a result-count terminal line."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    if not isinstance(out, dict):
        message = str(out)
        yield ctx.emit_tool_output_card({"status": "error", "message": message})
        yield ctx.streaming_service.format_terminal_info(message, "error")
        return

    hits = out.get("hits") or []
    yield ctx.emit_tool_output_card(
        {"status": "completed", "hits": hits, "count": len(hits)}
    )
    level = "success" if hits else "info"
    yield ctx.streaming_service.format_terminal_info(
        f"Found {len(hits)} result(s)", level
    )
