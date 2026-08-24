"""
RetryAfterMiddleware — Header-aware retry with custom backoff and SSE eventing.

LangChain's :class:`ModelRetryMiddleware` retries on exceptions but ignores
the ``Retry-After`` HTTP header — it just runs its own exponential backoff.
That wastes time when a provider has explicitly told us how long to wait.
This middleware honors the header (mirroring OpenCode's
``packages/opencode/src/session/llm.ts`` retry pathway) and emits an SSE
event so the UI can show "rate-limited, retrying in Ns".

We can't subclass ``ModelRetryMiddleware`` cleanly because its loop calls a
module-level ``calculate_delay`` inline (no overridable
``_calculate_delay`` hook), so this is a standalone implementation.

Behaviour:
- Extracts ``Retry-After`` / ``retry-after-ms`` from
  ``litellm.exceptions.RateLimitError.response.headers`` (or any exception
  exposing a similar shape).
- Sleeps ``max(exponential_backoff, header_delay)`` between retries,
  capped at ``max_delay``.
- Returns ``False`` from ``retry_on`` for context overflow so
  :class:`SurfSenseCompactionMiddleware` (or the LangChain summarization
  fallback path) handles it instead, and for the other categories a retry
  cannot fix (auth, permissions, unknown model, bad request, host out of
  memory).
- Emits ``surfsense.retrying`` via ``adispatch_custom_event`` on each retry
  so ``stream_new_chat`` can forward it to clients as an SSE event.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from collections.abc import Awaitable, Callable, Mapping
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

from app.observability import metrics as ot_metrics, otel as ot
from app.services.llm_error_adapter import LLMErrorCategory, adapt_llm_exception

logger = logging.getLogger(__name__)

# Categories for which a retry cannot help — context overflow needs
# compaction, auth needs human intervention, and a host that could not fit the
# model has already exhausted its own recovery (Ollama's scheduler retries a
# load-time OOM by shrinking an automatic context and evicting other models
# before it ever returns the error). Anything unrecognised stays retryable, so
# a transient failure we cannot classify still gets its attempts.
_NON_RETRYABLE_CATEGORIES: frozenset[LLMErrorCategory] = frozenset(
    {
        LLMErrorCategory.AUTH_FAILED,
        LLMErrorCategory.PERMISSION_DENIED,
        LLMErrorCategory.MODEL_NOT_FOUND,
        LLMErrorCategory.BAD_REQUEST,
        LLMErrorCategory.CONTEXT_LIMIT,
        LLMErrorCategory.INSUFFICIENT_MEMORY,
    }
)


def _is_non_retryable(exc: BaseException) -> bool:
    """Classify by message and wrapper chain, not just the exception class.

    Local runtimes surface both of the hopeless cases -- out of memory and
    context overflow -- as a generic provider error whose class name says
    nothing, so a class-name test retries them until the attempts run out.
    """
    return adapt_llm_exception(exc).category in _NON_RETRYABLE_CATEGORIES


def _extract_retry_after_seconds(exc: BaseException) -> float | None:
    """Return seconds-to-wait suggested by the provider, if any.

    Looks at ``exc.response.headers`` or ``exc.headers`` for the standard
    HTTP ``Retry-After`` header (in seconds) or its millisecond cousin
    ``retry-after-ms`` (sometimes used by Anthropic / OpenAI). Falls back
    to a regex on the exception message for shapes like
    ``"Please retry after 30s"``.
    """
    headers: Mapping[str, Any] | None = None
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
    if headers is None:
        headers = getattr(exc, "headers", None)

    # ``Mapping``, not ``dict``: litellm rebuilds the error's ``response`` as an
    # ``httpx.Response``, whose ``.headers`` is ``httpx.Headers`` -- a Mapping
    # that is not a dict subclass. A ``dict`` check silently skips every real
    # provider response.
    if isinstance(headers, Mapping):
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
        # ``max_delay`` caps the header hint as well as the backoff: this loop
        # runs inside the live turn, holding the SSE stream, the thread's busy
        # lock and the DB session for whatever it sleeps.
        return min(max(backoff, header), self.max_delay)

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
                ot.add_event(
                    "model.retry.scheduled",
                    {
                        "retry.attempt": attempt + 1,
                        "retry.max": self.max_retries,
                        "retry.delay_ms": int(delay * 1000),
                        "retry.reason": ot_metrics.categorize_exception(exc),
                    },
                )
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
                ot.add_event(
                    "model.retry.scheduled",
                    {
                        "retry.attempt": attempt + 1,
                        "retry.max": self.max_retries,
                        "retry.delay_ms": int(delay * 1000),
                        "retry.reason": ot_metrics.categorize_exception(exc),
                    },
                )
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
