"""Fallback only on provider/network errors; let programming bugs raise."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import ModelFallbackMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain.agents.middleware.types import ModelRequest, ModelResponse
    from langchain_core.messages import AIMessage


# Matched by class name across the MRO so we don't have to import every
# provider SDK (openai/anthropic/google/...). Extend as new providers ship.
_FALLBACK_ELIGIBLE_NAMES: frozenset[str] = frozenset(
    {
        "RateLimitError",
        "APIStatusError",
        "InternalServerError",
        "ServiceUnavailableError",
        "BadGatewayError",
        "GatewayTimeoutError",
        "APIConnectionError",
        "APITimeoutError",
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "RemoteProtocolError",
        "TimeoutError",
        "TimeoutException",
    }
)


def _is_fallback_eligible(exc: BaseException) -> bool:
    return any(cls.__name__ in _FALLBACK_ELIGIBLE_NAMES for cls in type(exc).__mro__)


class ScopedModelFallbackMiddleware(ModelFallbackMiddleware):
    """Re-raise non-provider exceptions instead of walking the fallback chain."""

    def wrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any] | AIMessage:
        last_exception: Exception
        try:
            return handler(request)
        except Exception as e:
            if not _is_fallback_eligible(e):
                raise
            last_exception = e

        for fallback_model in self.models:
            try:
                return handler(request.override(model=fallback_model))
            except Exception as e:
                if not _is_fallback_eligible(e):
                    raise
                last_exception = e
                continue

        raise last_exception

    async def awrap_model_call(  # type: ignore[override]
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any] | AIMessage:
        last_exception: Exception
        try:
            return await handler(request)
        except Exception as e:
            if not _is_fallback_eligible(e):
                raise
            last_exception = e

        for fallback_model in self.models:
            try:
                return await handler(request.override(model=fallback_model))
            except Exception as e:
                if not _is_fallback_eligible(e):
                    raise
                last_exception = e
                continue

        raise last_exception
