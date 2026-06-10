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
    status = out.get("status") if isinstance(out, dict) else None
    title = out.get("title", "Podcast") if isinstance(out, dict) else "Podcast"
    if status in (
        "awaiting_brief",
        "awaiting_review",
        "pending",
        "drafting",
        "rendering",
    ):
        yield ctx.streaming_service.format_terminal_info(
            f"Podcast brief ready to review: {title}",
            "success",
        )
    elif status in ("ready", "success"):
        yield ctx.streaming_service.format_terminal_info(
            f"Podcast generated successfully: {title}",
            "success",
        )
    elif status in ("failed", "error"):
        error_msg = out.get("error", "Unknown error") if isinstance(out, dict) else "Unknown error"
        yield ctx.streaming_service.format_terminal_info(
            f"Podcast generation failed: {error_msg}",
            "error",
        )
