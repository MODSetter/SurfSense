"""Async retry decorators for connector API calls, built on tenacity."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)

from app.connectors.exceptions import (
    ConnectorAPIError,
    ConnectorAuthError,
    ConnectorError,
    ConnectorRateLimitError,
    ConnectorTimeoutError,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ConnectorError):
        return exc.retryable
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False


def build_retry(
    *,
    max_attempts: int = 4,
    max_delay: float = 60.0,
    initial_delay: float = 1.0,
    total_timeout: float = 180.0,
    service: str = "",
) -> Callable:
    """Configurable tenacity ``@retry`` decorator with exponential backoff + jitter."""
    _logger = logging.getLogger(f"connector.retry.{service}") if service else logger

    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=(stop_after_attempt(max_attempts) | stop_after_delay(total_timeout)),
        wait=wait_exponential_jitter(initial=initial_delay, max=max_delay),
        reraise=True,
        before_sleep=before_sleep_log(_logger, logging.WARNING),
    )


def retry_on_transient(
    *,
    service: str = "",
    max_attempts: int = 4,
) -> Callable:
    """Shorthand: retry up to *max_attempts* on rate-limits, timeouts, and 5xx."""
    return build_retry(max_attempts=max_attempts, service=service)


def raise_for_status(
    response: httpx.Response,
    *,
    service: str = "",
) -> None:
    """Map non-2xx httpx responses to the appropriate ``ConnectorError``."""
    if response.is_success:
        return

    status = response.status_code

    try:
        body = response.json()
    except Exception:
        body = response.text[:500] if response.text else None

    if status == 429:
        retry_after_raw = response.headers.get("Retry-After")
        retry_after: float | None = None
        if retry_after_raw:
            try:
                retry_after = float(retry_after_raw)
            except (ValueError, TypeError):
                pass
        raise ConnectorRateLimitError(
            f"{service} rate limited (429)",
            service=service,
            retry_after=retry_after,
            response_body=body,
        )

    if status in (401, 403):
        raise ConnectorAuthError(
            f"{service} authentication failed ({status})",
            service=service,
            status_code=status,
            response_body=body,
        )

    if status == 504:
        raise ConnectorTimeoutError(
            f"{service} gateway timeout (504)",
            service=service,
            status_code=status,
            response_body=body,
        )

    if status >= 500:
        raise ConnectorAPIError(
            f"{service} server error ({status})",
            service=service,
            status_code=status,
            response_body=body,
        )

    raise ConnectorAPIError(
        f"{service} request failed ({status})",
        service=service,
        status_code=status,
        response_body=body,
    )
