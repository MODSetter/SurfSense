"""generate_video_presentation: tool card + terminal line."""

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
    if not isinstance(out, dict):
        return
    status = out.get("status")
    # ``ready`` is the live success status now that the tool waits for the
    # Celery worker to reach a terminal state. ``pending`` is retained as a
    # legacy branch for old saved chats that pre-date the wait-for-terminal
    # change (see ``app.agents.shared.deliverable_wait``).
    if status == "ready":
        yield ctx.streaming_service.format_terminal_info(
            f"Video presentation generated successfully: {out.get('title', 'Presentation')}",
            "success",
        )
    elif status == "pending":
        yield ctx.streaming_service.format_terminal_info(
            f"Video presentation queued: {out.get('title', 'Presentation')}",
            "success",
        )
    elif status == "failed":
        error_msg = out.get("error", "Unknown error")
        yield ctx.streaming_service.format_terminal_info(
            f"Presentation generation failed: {error_msg}",
            "error",
        )
