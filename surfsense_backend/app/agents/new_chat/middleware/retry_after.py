"""
RetryAfterMiddleware — Header-aware retry with custom backoff and SSE eventing.

Why standalone instead of subclassing ``ModelRetryMiddleware``: the upstream
class calls module-level ``calculate_delay`` inline (no overridable
``_calculate_delay`` hook), so a subclass cannot inject Retry-After header
delays without rewriting the loop. Tier 1.4 in the OpenCode-port plan.

Behaviour:
- Extracts ``Retry-After`` / ``retry-after-ms`` from
  ``litellm.exceptions.RateLimitError.response.headers`` (or any exception
  exposing a similar shape).
- Sleeps ``max(exponential_backoff, header_delay)`` between retries.
- Returns ``False`` from ``retry_on`` for ``ContextWindowExceededError`` /
  ``ContextOverflowError`` so :class:`SurfSenseCompactionMiddleware` (or
  the LangChain summarization fallback path) handles those instead.
- Emits ``surfsense.retrying`` via ``adispatch_custom_event`` on each retry
  so ``stream_new_chat`` can forward it to clients as an SSE event.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)
from langchain_core.callbacks import adispatch_custom_event, dispatch_custom_event
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

# Names of exception classes for which a retry would not help — context
# overflow needs compaction, auth needs human intervention, etc. Detected
# by class-name substring so we don't have to import LiteLLM/Anthropic
# here (which would tie this module to optional deps).
_NON_RETRYABLE_NAME_HINTS: tuple[str, ...] = (
    "ContextWindowExceeded",
    "ContextOverflow",
    "AuthenticationError",
    "InvalidRequestError",
    "PermissionDenied",
    "InvalidApiKey",
    "ContextLimit",
)


def _is_non_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__
    return any(hint in name for hint in _NON_RETRYABLE_NAME_HINTS)


def _extract_retry_after_seconds(exc: BaseException) -> float | None:
    """Return seconds-to-wait suggested by the provider, if any.

    Looks at ``exc.response.headers`` or ``exc.headers`` for the standard
    HTTP ``Retry-After`` header (in seconds) or its millisecond cousin
    ``retry-after-ms`` (sometimes used by Anthropic / OpenAI). Falls back
    to a regex on the exception message for shapes like
    ``"Please retry after 30s"``.
    """
    headers: dict[str, Any] | None = None
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
    if headers is None:
        headers = getattr(exc, "headers", None)

    if isinstance(headers, dict):
        # Normalize keys to lowercase for case-insensitive matching
        norm = {str(k).lower(): v for k, v in headers.items()}
        ms = norm.get("retry-after-ms")
        if ms is not None:
            try:
                return float(ms) / 1000.0
            except (TypeError, ValueError):
                pass
        seconds = norm.get("retry-after")
        if seconds is not None:
            try:
                return float(seconds)
            except (TypeError, ValueError):
                pass

    # Last resort: scan the message for "retry after Xs" or "X seconds"
    msg = str(exc)
    match = re.search(r"retry\s+after\s+([0-9]+(?:\.[0-9]+)?)", msg, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _exponential_delay(
    attempt: int,
    *,
    initial_delay: float,
    backoff_factor: float,
    max_delay: float,
    jitter: bool,
) -> float:
    """Compute an exponential-backoff delay with optional ±25% jitter."""
    delay = (
        initial_delay * (backoff_factor**attempt) if backoff_factor else initial_delay
    )
    delay = min(delay, max_delay)
    if jitter and delay > 0:
        delay *= 1 + random.uniform(-0.25, 0.25)
    return max(delay, 0.0)


class RetryAfterMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Retry middleware that honors provider-issued Retry-After hints.

    Drop-in replacement for :class:`langchain.agents.middleware.ModelRetryMiddleware`
    when working with LiteLLM/Anthropic/OpenAI providers that surface
    rate-limit hints in headers. Always emits ``surfsense.retrying`` SSE
    events so the UI can show a friendly "rate limited, retrying in Xs"
    indicator.

    Args:
        max_retries: Maximum retries after the initial attempt (default 3).
        initial_delay: Initial backoff delay in seconds.
        backoff_factor: Exponential growth factor for backoff.
        max_delay: Cap on per-attempt delay in seconds.
        jitter: Whether to add ±25% jitter.
        retry_on: Optional callable that returns True for retryable
            exceptions. The default retries everything except known
            non-retryable classes (context overflow, auth, etc.).
    """

    def __init__(
        self,
        *,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        retry_on: Callable[[BaseException], bool] | None = None,
    ) -> None:
        super().__init__()
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.jitter = jitter
        self._retry_on: Callable[[BaseException], bool] = retry_on or (
            lambda exc: not _is_non_retryable(exc)
        )

    def _should_retry(self, exc: BaseException) -> bool:
        try:
            return bool(self._retry_on(exc))
        except Exception:
            logger.exception("retry_on callable raised; defaulting to False")
            return False

    def _delay_for_attempt(self, attempt: int, exc: BaseException) -> float:
        backoff = _exponential_delay(
            attempt,
            initial_delay=self.initial_delay,
            backoff_factor=self.backoff_factor,
            max_delay=self.max_delay,
            jitter=self.jitter,
        )
        header = _extract_retry_after_seconds(exc) or 0.0
        return max(backoff, header)

    def wrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        for attempt in range(self.max_retries + 1):
            try:
                return handler(request)
            except Exception as exc:
                if not self._should_retry(exc) or attempt >= self.max_retries:
                    raise
                delay = self._delay_for_attempt(attempt, exc)
                try:
                    dispatch_custom_event(
                        "surfsense.retrying",
                        {
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "delay_ms": int(delay * 1000),
                            "reason": type(exc).__name__,
                        },
                    )
                except Exception:
                    logger.debug(
                        "dispatch_custom_event failed; suppressed", exc_info=True
                    )
                if delay > 0:
                    time.sleep(delay)
        # Unreachable
        raise RuntimeError("RetryAfterMiddleware: retry loop exited without resolution")

    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[ContextT],
        handler: Callable[
            [ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]
        ],
    ) -> ModelResponse[ResponseT] | AIMessage:
        for attempt in range(self.max_retries + 1):
            try:
                return await handler(request)
            except Exception as exc:
                if not self._should_retry(exc) or attempt >= self.max_retries:
                    raise
                delay = self._delay_for_attempt(attempt, exc)
                try:
                    await adispatch_custom_event(
                        "surfsense.retrying",
                        {
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "delay_ms": int(delay * 1000),
                            "reason": type(exc).__name__,
                        },
                    )
                except Exception:
                    logger.debug(
                        "adispatch_custom_event failed; suppressed", exc_info=True
                    )
                if delay > 0:
                    await asyncio.sleep(delay)
        raise RuntimeError("RetryAfterMiddleware: retry loop exited without resolution")


__all__ = [
    "RetryAfterMiddleware",
    "_extract_retry_after_seconds",
    "_is_non_retryable",
]
