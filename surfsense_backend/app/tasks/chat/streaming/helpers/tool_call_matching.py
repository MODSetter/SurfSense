"""Match buffered model tool-call chunks to a tool start when ids were missing."""

from __future__ import annotations

from typing import Any


def match_buffered_langchain_tool_call_id(
    pending_tool_call_chunks: list[dict[str, Any]],
    tool_name: str,
    run_id: str,
    lc_tool_call_id_by_run: dict[str, str],
) -> str | None:
    matched_idx: int | None = None
    for idx, tcc in enumerate(pending_tool_call_chunks):
        if tcc.get("name") == tool_name and tcc.get("id"):
            matched_idx = idx
            break
    if matched_idx is None:
        for idx, tcc in enumerate(pending_tool_call_chunks):
            if tcc.get("id"):
                matched_idx = idx
                break
    if matched_idx is None:
        return None
    matched = pending_tool_call_chunks.pop(matched_idx)
    candidate = matched.get("id")
    if isinstance(candidate, str) and candidate:
        if run_id:
            lc_tool_call_id_by_run[run_id] = candidate
        return candidate
    return None
