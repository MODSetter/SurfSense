"""generate_podcast: tool card + queue / success / failure terminal lines."""

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
    if isinstance(out, dict) and out.get("status") in (
        "pending",
        "generating",
        "processing",
    ):
        yield ctx.streaming_service.format_terminal_info(
            f"Podcast queued: {out.get('title', 'Podcast')}",
            "success",
        )
    elif isinstance(out, dict) and out.get("status") in ("ready", "success"):
        yield ctx.streaming_service.format_terminal_info(
            f"Podcast generated successfully: {out.get('title', 'Podcast')}",
            "success",
        )
    elif isinstance(out, dict) and out.get("status") in ("failed", "error"):
        error_msg = out.get("error", "Unknown error")
        yield ctx.streaming_service.format_terminal_info(
            f"Podcast generation failed: {error_msg}",
            "error",
        )
