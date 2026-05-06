"""generate_report: thinking-step copy."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.deliverables.shared.tool_input import (
    as_tool_input_dict,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    d = as_tool_input_dict(tool_input)
    report_topic = (
        d.get("topic", "Report") if isinstance(tool_input, dict) else "Report"
    )
    is_revision = bool(
        isinstance(tool_input, dict) and tool_input.get("parent_report_id")
    )
    step_title = "Revising report" if is_revision else "Generating report"
    return ToolStartThinking(
        title=step_title,
        items=[f"Topic: {report_topic}", "Analyzing source content..."],
    )


def resolve_completed_thinking(
    tool_name: str, tool_output: Any, last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    report_status = (
        tool_output.get("status", "unknown")
        if isinstance(tool_output, dict)
        else "unknown"
    )
    report_title = (
        tool_output.get("title", "Report")
        if isinstance(tool_output, dict)
        else "Report"
    )
    word_count = (
        tool_output.get("word_count", 0)
        if isinstance(tool_output, dict)
        else 0
    )
    is_revision = (
        tool_output.get("is_revision", False)
        if isinstance(tool_output, dict)
        else False
    )
    step_title = "Revising report" if is_revision else "Generating report"

    if report_status == "ready":
        completed = [
            f"Topic: {report_title}",
            f"{word_count:,} words",
            "Report ready",
        ]
    elif report_status == "failed":
        error_msg = (
            tool_output.get("error", "Unknown error")
            if isinstance(tool_output, dict)
            else "Unknown error"
        )
        completed = [
            f"Topic: {report_title}",
            f"Error: {error_msg[:50]}",
        ]
    else:
        completed = items

    return (step_title, completed)
