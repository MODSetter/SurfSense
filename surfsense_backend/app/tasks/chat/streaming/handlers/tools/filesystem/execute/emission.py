"""execute: exit code, stdout, sandbox file hints."""

from __future__ import annotations

import re
from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    raw_text = out.get("result", "") if isinstance(out, dict) else str(out)
    exit_code: int | None = None
    output_text = raw_text
    m = re.match(r"^Exit code:\s*(\d+)", raw_text)
    if m:
        exit_code = int(m.group(1))
        om = re.search(r"\nOutput:\n([\s\S]*)", raw_text)
        output_text = om.group(1) if om else ""
    thread_id_str = ctx.langgraph_config.get("configurable", {}).get("thread_id", "")

    for sf_match in re.finditer(
        r"^SANDBOX_FILE:\s*(.+)$", output_text, re.MULTILINE
    ):
        fpath = sf_match.group(1).strip()
        if fpath and fpath not in ctx.stream_result.sandbox_files:
            ctx.stream_result.sandbox_files.append(fpath)

    yield ctx.emit_tool_output_card(
        {
            "exit_code": exit_code,
            "output": output_text,
            "thread_id": thread_id_str,
        },
    )
