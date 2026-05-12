"""Split a model chunk into text, reasoning, and tool-call fragment lists."""

from __future__ import annotations

from typing import Any


def extract_chunk_parts(chunk: Any) -> dict[str, Any]:
    """Return dict with keys text, reasoning, and tool_call_chunks (merged from chunk fields)."""
    out: dict[str, Any] = {"text": "", "reasoning": "", "tool_call_chunks": []}
    if chunk is None:
        return out

    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        if content:
            out["text"] = content
    elif isinstance(content, list):
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                value = block.get("text") or block.get("content") or ""
                if isinstance(value, str) and value:
                    text_parts.append(value)
            elif block_type == "reasoning":
                value = (
                    block.get("reasoning")
                    or block.get("text")
                    or block.get("content")
                    or ""
                )
                if isinstance(value, str) and value:
                    reasoning_parts.append(value)
            elif block_type in ("tool_call_chunk", "tool_use"):
                out["tool_call_chunks"].append(block)
        if text_parts:
            out["text"] = "".join(text_parts)
        if reasoning_parts:
            out["reasoning"] = "".join(reasoning_parts)

    additional = getattr(chunk, "additional_kwargs", None) or {}
    if isinstance(additional, dict):
        extra_reasoning = additional.get("reasoning_content")
        if isinstance(extra_reasoning, str) and extra_reasoning:
            existing = out["reasoning"]
            out["reasoning"] = (
                (existing + extra_reasoning) if existing else extra_reasoning
            )

    extra_tool_chunks = getattr(chunk, "tool_call_chunks", None)
    if isinstance(extra_tool_chunks, list):
        for tcc in extra_tool_chunks:
            if isinstance(tcc, dict):
                out["tool_call_chunks"].append(tcc)

    return out
