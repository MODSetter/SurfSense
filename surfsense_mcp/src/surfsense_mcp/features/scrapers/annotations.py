"""Tool-call policy hints shared across scraper tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

SCRAPE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)

READ_RUNS = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
