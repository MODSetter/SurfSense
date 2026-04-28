"""
Typed error taxonomy for the SurfSense agent stack.

Used by:
- :class:`RetryAfterMiddleware` (Tier 1.4) — its ``retry_on`` callable
  consults the error code to decide whether a retry is appropriate.
- :class:`PermissionMiddleware` (Tier 2.1) — emits
  ``code="permission_denied"`` errors when a deny rule trips.
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


class RejectedError(Exception):
    """Raised when the user rejects a permission ask without feedback.

    Caught by :class:`PermissionMiddleware`; the agent stops the current
    tool fan-out and surfaces a user-facing rejection.
    """

    def __init__(self, *, tool: str | None = None, pattern: str | None = None) -> None:
        super().__init__(f"Permission rejected for tool {tool!r}, pattern {pattern!r}")
        self.tool = tool
        self.pattern = pattern


class CorrectedError(Exception):
    """Raised when the user rejects a permission ask *with* feedback.

    The :class:`PermissionMiddleware` translates the feedback into a
    synthetic ``ToolMessage`` so the model sees the user's correction
    and can retry the request differently.
    """

    def __init__(self, feedback: str, *, tool: str | None = None) -> None:
        super().__init__(feedback)
        self.feedback = feedback
        self.tool = tool


class BusyError(Exception):
    """Raised when a second prompt arrives while the same thread is mid-stream."""

    def __init__(self, request_id: str | None = None) -> None:
        super().__init__("Thread is busy with another request")
        self.request_id = request_id


__all__ = [
    "BusyError",
    "CorrectedError",
    "ErrorCode",
    "RejectedError",
    "StreamingError",
]
