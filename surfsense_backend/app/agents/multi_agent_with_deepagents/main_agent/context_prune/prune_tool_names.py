"""Tool names excluded from context-editing prune when bound."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool

PRUNE_PROTECTED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "generate_report",
        "generate_resume",
        "generate_podcast",
        "generate_video_presentation",
        "generate_image",
        "read_email",
        "search_emails",
        "invalid",
    },
)


def safe_exclude_tools(tools: Sequence[BaseTool]) -> tuple[str, ...]:
    """Names from ``PRUNE_PROTECTED_TOOL_NAMES`` that appear in ``tools``."""
    enabled = {t.name for t in tools}
    return tuple(n for n in PRUNE_PROTECTED_TOOL_NAMES if n in enabled)
