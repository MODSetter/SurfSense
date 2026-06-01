"""Filter approval-required tools from gateway agent invocations."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

DEFAULT_HITL_TOOL_NAMES = {
    "delete_document",
    "delete_folder",
    "delete_note",
    "delete_report",
    "delete_connector",
    "send_email",
    "share_chat",
}


def _tool_name(tool: Any) -> str | None:
    if isinstance(tool, str):
        return tool
    return getattr(tool, "name", None) or getattr(tool, "__name__", None)


def filter_hitl_tools(
    toolkit: Iterable[Any] | None,
    *,
    blocked_names: set[str] | None = None,
) -> list[Any] | None:
    """Return a toolkit with known approval-required tools removed."""
    if toolkit is None:
        return None
    blocked = blocked_names or DEFAULT_HITL_TOOL_NAMES
    return [tool for tool in toolkit if (_tool_name(tool) or "") not in blocked]

