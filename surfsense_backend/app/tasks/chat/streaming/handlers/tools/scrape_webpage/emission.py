"""scrape_webpage: redacted payload + terminal summary."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    if isinstance(out, dict):
        display_output = {k: v for k, v in out.items() if k != "content"}
        if "content" in out:
            content = out.get("content", "")
            display_output["content_preview"] = (
                content[:500] + "..." if len(content) > 500 else content
            )
        yield ctx.emit_tool_output_card(display_output)
    else:
        yield ctx.emit_tool_output_card({"result": out})

    if isinstance(out, dict) and "error" not in out:
        title = out.get("title", "Webpage")
        word_count = out.get("word_count", 0)
        yield ctx.streaming_service.format_terminal_info(
            f"Scraped: {title[:40]}{'...' if len(title) > 40 else ''} ({word_count:,} words)",
            "success",
        )
    else:
        error_msg = (
            out.get("error", "Failed to scrape")
            if isinstance(out, dict)
            else "Failed to scrape"
        )
        yield ctx.streaming_service.format_terminal_info(
            f"Scrape failed: {error_msg}",
            "error",
        )
