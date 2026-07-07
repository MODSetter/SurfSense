"""web_scrape: per-page card (content previewed) + a scraped-count terminal line."""

from __future__ import annotations

from collections.abc import Iterator

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)

_PREVIEW_CHARS = 500


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    out = ctx.tool_output
    if not isinstance(out, dict):
        message = str(out)
        yield ctx.emit_tool_output_card({"status": "error", "message": message})
        yield ctx.streaming_service.format_terminal_info(message, "error")
        return

    rows = out.get("rows") or []
    pages = [_page(row) for row in rows]
    succeeded = sum(1 for row in rows if row.get("status") == "success")

    yield ctx.emit_tool_output_card(
        {
            "status": "completed",
            "pages": pages,
            "succeeded": succeeded,
            "total": len(rows),
        }
    )
    level = "success" if succeeded else "error"
    yield ctx.streaming_service.format_terminal_info(
        f"Scraped {succeeded}/{len(rows)} page(s)", level
    )


def _page(row: dict) -> dict:
    """A card-safe view of one row: metadata kept, content bounded to a preview."""
    page: dict = {"url": row.get("url"), "status": row.get("status")}
    if row.get("metadata"):
        page["metadata"] = row["metadata"]
    content = row.get("content")
    if content:
        page["content_preview"] = (
            content[:_PREVIEW_CHARS] + "…" if len(content) > _PREVIEW_CHARS else content
        )
    if row.get("error"):
        page["error"] = row["error"]
    return page
