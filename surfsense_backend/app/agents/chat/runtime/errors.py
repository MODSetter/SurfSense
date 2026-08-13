"""
Typed error taxonomy for the SurfSense agent stack.

Used by:
- :class:`RetryAfterMiddleware` — its ``retry_on`` callable consults
  the error code to decide whether a retry is appropriate.
- :class:`PermissionMiddleware` — emits ``code="permission_denied"``
  errors when a deny rule trips.
- All tools — return :class:`StreamingError` payloads in
  ``ToolMessage.additional_kwargs["error"]`` so the model and the
  retry/permission layers share a contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ErrorCode = Literal[
    "rate_limit",
    "auth",
    "tool_validation",
    "tool_runtime",
    "context_overflow",
    "provider",
    "permission_denied",
    "doom_loop",
    "busy",
    "cancelled",
]


class StreamingError(BaseModel):
    """Structured error payload attached to ``ToolMessage.additional_kwargs["error"]``.

    Tools and middleware emit this so retry, permission, and routing
    layers can decide what to do without parsing free-form strings.
    """

    code: ErrorCode
    retryable: bool = False
    suggestion: str | None = None
    correlation_id: str | None = None
    detail: str | None = Field(
        default=None,
        description="Free-form additional context. Not surfaced to the model.",
    )

    class Config:
        frozen = True


class BusyError(Exception):
    """Raised when a second prompt arrives while the same thread is mid-stream."""

    def __init__(self, request_id: str | None = None) -> None:
        super().__init__("Thread is busy with another request")
        self.request_id = request_id


__all__ = [
    "BusyError",
    "ErrorCode",
    "StreamingError",
]
