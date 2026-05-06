"""Emit one terminal error SSE frame and log via the stream error classifier."""

from __future__ import annotations

from typing import Any, Literal

from .classifier import log_chat_stream_error


def emit_stream_terminal_error(
    *,
    streaming_service: Any,
    flow: Literal["new", "resume", "regenerate"],
    request_id: str | None,
    thread_id: int,
    search_space_id: int,
    user_id: str | None,
    message: str,
    error_kind: str = "server_error",
    error_code: str = "SERVER_ERROR",
    severity: Literal["info", "warn", "error"] = "error",
    is_expected: bool = False,
    extra: dict[str, Any] | None = None,
) -> str:
    log_chat_stream_error(
        flow=flow,
        error_kind=error_kind,
        error_code=error_code,
        severity=severity,
        is_expected=is_expected,
        request_id=request_id,
        thread_id=thread_id,
        search_space_id=search_space_id,
        user_id=user_id,
        message=message,
        extra=extra,
    )
    return streaming_service.format_error(message, error_code=error_code, extra=extra)
