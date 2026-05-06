"""write_file: path + status envelope on the tool-output card."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)
from app.tasks.chat.streaming.helpers.tool_output import (
    extract_resolved_file_path,
    tool_output_has_error,
    tool_output_to_text,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    resolved_path = extract_resolved_file_path(
        tool_name=ctx.tool_name,
        tool_output=ctx.tool_output,
        tool_input={"file_path": ctx.staged_workspace_file_path}
        if ctx.staged_workspace_file_path
        else None,
    )
    result_text = tool_output_to_text(ctx.tool_output)
    if tool_output_has_error(ctx.tool_output):
        yield ctx.emit_tool_output_card(
            {
                "status": "error",
                "error": result_text,
                "path": resolved_path,
            },
        )
    else:
        yield ctx.emit_tool_output_card(
            {
                "status": "completed",
                "path": resolved_path,
                "result": result_text,
            },
        )
