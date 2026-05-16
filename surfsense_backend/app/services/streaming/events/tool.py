"""Tool-call streaming events.

``toolCallId`` and ``langchainToolCallId`` are AI SDK protocol fields
and stay camelCase. Sub-agent provenance rides on the snake_case
top-level ``emitted_by`` envelope added by :func:`attach_emitted_by`.
"""

from __future__ import annotations

from typing import Any

from ..emitter import Emitter, attach_emitted_by
from ..envelope import format_sse


def format_tool_input_start(
    tool_call_id: str,
    tool_name: str,
    *,
    langchain_tool_call_id: str | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "tool-input-start",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
    }
    if langchain_tool_call_id:
        payload["langchainToolCallId"] = langchain_tool_call_id
    return format_sse(attach_emitted_by(payload, emitter))


def format_tool_input_delta(
    tool_call_id: str,
    input_text_delta: str,
    *,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "tool-input-delta",
        "toolCallId": tool_call_id,
        "inputTextDelta": input_text_delta,
    }
    return format_sse(attach_emitted_by(payload, emitter))


def format_tool_input_available(
    tool_call_id: str,
    tool_name: str,
    input_data: dict[str, Any],
    *,
    langchain_tool_call_id: str | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "tool-input-available",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
        "input": input_data,
    }
    if langchain_tool_call_id:
        payload["langchainToolCallId"] = langchain_tool_call_id
    return format_sse(attach_emitted_by(payload, emitter))


def format_tool_output_available(
    tool_call_id: str,
    output: Any,
    *,
    langchain_tool_call_id: str | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "tool-output-available",
        "toolCallId": tool_call_id,
        "output": output,
    }
    if langchain_tool_call_id:
        payload["langchainToolCallId"] = langchain_tool_call_id
    return format_sse(attach_emitted_by(payload, emitter))
