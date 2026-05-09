"""scrape_webpage: thinking-step copy."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.handlers.tools.scrape_webpage.shared.tool_input import (
    as_tool_input_dict,
)
from app.tasks.chat.streaming.handlers.tools.shared.model import (
    ToolStartThinking,
)


def resolve_start_thinking(tool_name: str, tool_input: Any) -> ToolStartThinking:
    del tool_name
    d = as_tool_input_dict(tool_input)
    url = d.get("url", "") if isinstance(tool_input, dict) else str(tool_input)
    return ToolStartThinking(
        title="Scraping webpage",
        items=[f"URL: {url[:80]}{'...' if len(url) > 80 else ''}"],
    )


def resolve_completed_thinking(
    tool_name: str, tool_output: Any, last_items: list[str],
) -> tuple[str, list[str]]:
    del tool_name
    items = last_items
    if isinstance(tool_output, dict):
        title = tool_output.get("title", "Webpage")
        word_count = tool_output.get("word_count", 0)
        has_error = "error" in tool_output
        if has_error:
            completed = [
                *items,
                f"Error: {tool_output.get('error', 'Failed to scrape')[:50]}",
            ]
        else:
            completed = [
                *items,
                f"Title: {title[:50]}{'...' if len(title) > 50 else ''}",
                f"Extracted: {word_count:,} words",
            ]
    else:
        completed = [*items, "Content extracted"]
    return ("Scraping webpage", completed)
