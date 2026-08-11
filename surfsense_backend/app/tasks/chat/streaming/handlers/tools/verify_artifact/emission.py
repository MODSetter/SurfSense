"""Forward the verification verdict to its timeline card."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    output = ctx.tool_output
    payload = output if isinstance(output, dict) else {"result": output}
    yield ctx.emit_tool_output_card(payload)
    verified = isinstance(output, dict) and output.get("status") == "verified"
    unavailable = verified and bool(output.get("verification_unavailable"))
    if unavailable:
        text = "Artifact verification completed without visual review"
        message_type = "info"
    elif verified:
        text = "Artifact verification complete"
        message_type = "success"
    else:
        text = "Artifact verification found issues"
        message_type = "error"
    yield ctx.streaming_service.format_terminal_info(
        text,
        message_type,
    )
