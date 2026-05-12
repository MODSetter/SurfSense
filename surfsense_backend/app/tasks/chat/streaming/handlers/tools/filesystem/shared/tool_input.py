"""Tool-call args + display truncation for filesystem thinking modules."""

from __future__ import annotations

from typing import Any


def as_tool_input_dict(tool_input: Any) -> dict[str, Any]:
    return tool_input if isinstance(tool_input, dict) else {}


def truncate_path(fp: str, *, max_len: int = 80) -> str:
    return fp if len(fp) <= max_len else "…" + fp[-(max_len - 3) :]


def truncate_middle(s: str, *, max_len: int = 60) -> str:
    return s if len(s) <= max_len else "…" + s[-(max_len - 3) :]
