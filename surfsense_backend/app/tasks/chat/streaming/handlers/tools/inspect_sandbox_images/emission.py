"""Forward the QA report so the page-review card can render it.

Without this module the tool resolves to ``default.emission``, which sends
only ``result_length`` — the card then has nothing to show and renders its
empty state even though the model received the full report.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    report = out.get("result", "") if isinstance(out, dict) else str(out)
    yield ctx.emit_tool_output_card({"result": report})
    yield ctx.streaming_service.format_terminal_info(
        f"Tool {ctx.tool_name} completed",
        "success",
    )
