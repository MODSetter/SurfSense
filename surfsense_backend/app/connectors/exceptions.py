"""Standard exception hierarchy for all connectors.

ConnectorError
├── ConnectorAuthError         (401/403 — non-retryable)
├── ConnectorRateLimitError    (429 — retryable, carries ``retry_after``)
├── ConnectorTimeoutError      (timeout/504 — retryable)
└── ConnectorAPIError          (5xx or unexpected — retryable when >= 500)
"""

from __future__ import annotations

from typing import Any


class ConnectorError(Exception):
    def __init__(
        self,
        message: str,
        *,
        service: str = "",
        status_code: int | None = None,
        response_body: Any = None,
    ) -> None:
        super().__init__(message)
        self.service = service
        self.status_code = status_code
        self.response_body = response_body

    @property
    def retryable(self) -> bool:
        return False


class ConnectorAuthError(ConnectorError):
    """Token expired, revoked, insufficient scopes, or needs re-auth (401/403)."""

    @property
    def retryable(self) -> bool:
        return False


class ConnectorRateLimitError(ConnectorError):
    """429 Too Many Requests."""

    def __init__(
        self,
        message: str = "Rate limited",
        *,
        service: str = "",
        retry_after: float | None = None,
        status_code: int = 429,
        response_body: Any = None,
    ) -> None:
        super().__init__(
            message,
            service=service,
            status_code=status_code,
            response_body=response_body,
        )
        self.retry_after = retry_after

    @property
    def retryable(self) -> bool:
        return True


class ConnectorTimeoutError(ConnectorError):
    """Request timeout or gateway timeout (504)."""

    def __init__(
        self,
        message: str = "Request timed out",
        *,
        service: str = "",
        status_code: int | None = None,
        response_body: Any = None,
    ) -> None:
        super().__init__(
            message,
            service=service,
            status_code=status_code,
            response_body=response_body,
        )

    @property
    def retryable(self) -> bool:
        return True


class ConnectorAPIError(ConnectorError):
    """Generic API error (5xx or unexpected status codes)."""

    @property
    def retryable(self) -> bool:
        if self.status_code is not None:
            return self.status_code >= 500
        return False
