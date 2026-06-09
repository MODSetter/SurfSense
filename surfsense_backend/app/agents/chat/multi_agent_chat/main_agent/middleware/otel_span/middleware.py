"""
OpenTelemetry span middleware for the SurfSense ``new_chat`` agent.

Wraps both ``model.call`` (LLM invocations) and ``tool.call`` (tool
executions) with OTel spans, attaching low-cardinality span names and
high-cardinality identifiers as attributes.

This middleware is intentionally a thin adapter over
:mod:`app.observability.otel`; when OTel is not configured all spans
collapse to no-ops and the wrapper adds <1µs overhead per call. When
OTel **is** configured (``OTEL_EXPORTER_OTLP_ENDPOINT`` set), every
model and tool call gets a span with the standard attributes our
dashboards expect.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage

from app.observability import metrics as ot_metrics, otel as ot
from app.utils.perf import get_perf_logger

if TYPE_CHECKING:  # pragma: no cover — type-only
    from langchain.agents.middleware.types import (
        ModelRequest,
        ModelResponse,
        ToolCallRequest,
    )
    from langgraph.types import Command

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


class OtelSpanMiddleware(AgentMiddleware):
    """Emit ``model.call`` and ``tool.call`` OTel spans for every invocation.

    Should be placed near the **outer** end of the middleware list so
    that the spans encompass retry/fallback wrapper effects (i.e. ``N``
    model.call spans for ``N`` retry attempts) but inside any concurrency/
    auth gate. Empirically this means **between** ``BusyMutex`` and
    ``RetryAfter``.
    """

    def __init__(self, *, instrumentation_name: str = "surfsense.new_chat") -> None:
        super().__init__()
        self._instrumentation_name = instrumentation_name

    # ------------------------------------------------------------------
    # Model call spans
    # ------------------------------------------------------------------

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse | AIMessage | Any]],
    ) -> ModelResponse | AIMessage | Any:
        if not ot.is_enabled():
            # Always emit a [PERF] line for the model step even when OTel is
            # disabled. This isolates provider/model latency from the agent's
            # pre-flight (before_agent KB-priority/memory/tree) work, which is
            # the usual culprit when the multi-agent path feels slow to start.
            # ``perf_counter`` at entry doubles as the "before_agent finished /
            # model call started" marker on the first step of a turn.
            model_id, _provider = _resolve_model_attrs(request)
            _t0 = time.perf_counter()
            _perf_log.info("[model_call] start model=%s", model_id)
            try:
                return await handler(request)
            finally:
                _perf_log.info(
                    "[model_call] done model=%s elapsed=%.3fs",
                    model_id,
                    time.perf_counter() - _t0,
                )

        model_id, provider = _resolve_model_attrs(request)
        t0 = time.perf_counter()
        with ot.model_call_span(model_id=model_id, provider=provider) as sp:
            _annotate_model_request(sp, model_id=model_id, provider=provider)
            try:
                result = await handler(request)
            except Exception:
                ot_metrics.record_model_call_duration(
                    (time.perf_counter() - t0) * 1000,
                    model=model_id,
                    provider=provider,
                )
                # span context manager records + re-raises
                raise
            else:
                input_tokens, output_tokens = _annotate_model_response(
                    sp,
                    result,
                    model_id=model_id,
                    provider=provider,
                )
                ot_metrics.record_model_call_duration(
                    (time.perf_counter() - t0) * 1000,
                    model=model_id,
                    provider=provider,
                )
                ot_metrics.record_model_token_usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=model_id,
                    provider=provider,
                )
                return result

    # ------------------------------------------------------------------
    # Tool call spans
    # ------------------------------------------------------------------

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        if not ot.is_enabled():
            return await handler(request)

        tool_name = _resolve_tool_name(request)
        input_size = _resolve_input_size(request)

        t0 = time.perf_counter()
        with ot.tool_call_span(tool_name, input_size=input_size) as sp:
            try:
                result = await handler(request)
            except Exception:
                ot_metrics.record_tool_call_duration(
                    (time.perf_counter() - t0) * 1000,
                    tool_name=tool_name,
                )
                ot_metrics.record_tool_call_error(tool_name=tool_name)
                raise
            errored = _annotate_tool_result(sp, result)
            ot_metrics.record_tool_call_duration(
                (time.perf_counter() - t0) * 1000,
                tool_name=tool_name,
            )
            if errored:
                ot_metrics.record_tool_call_error(tool_name=tool_name)
            return result


# ---------------------------------------------------------------------------
# Attribute helpers (kept defensive; we never want OTel bookkeeping to break
# a real model/tool call).
# ---------------------------------------------------------------------------


def _resolve_model_attrs(request: Any) -> tuple[str | None, str | None]:
    """Extract ``model.id`` and ``model.provider`` from a ``ModelRequest``."""
    model_id: str | None = None
    provider: str | None = None
    try:
        model = getattr(request, "model", None)
        if model is None:
            return None, None
        # langchain BaseChatModel exposes a few different identifiers
        for attr in ("model_name", "model", "model_id"):
            value = getattr(model, attr, None)
            if value:
                model_id = str(value)
                break
        # provider sometimes lives on ``_llm_type`` (legacy) or ``provider``
        for attr in ("provider", "_llm_type"):
            value = getattr(model, attr, None)
            if value:
                provider = str(value)
                break
    except Exception:  # pragma: no cover — defensive
        pass
    return model_id, provider


def _resolve_tool_name(request: Any) -> str:
    try:
        tool = getattr(request, "tool", None)
        if tool is not None:
            name = getattr(tool, "name", None)
            if isinstance(name, str) and name:
                return name
        # Fall back to the tool_call dict
        call = getattr(request, "tool_call", None) or {}
        name = call.get("name") if isinstance(call, dict) else None
        if isinstance(name, str) and name:
            return name
    except Exception:  # pragma: no cover — defensive
        pass
    return "unknown"


def _resolve_input_size(request: Any) -> int | None:
    try:
        call = getattr(request, "tool_call", None)
        if not isinstance(call, dict) or not call:
            return None
        args = call.get("args")
        if args is None:
            return None
        return len(repr(args))
    except Exception:  # pragma: no cover — defensive
        return None


def _annotate_model_request(
    span: Any, *, model_id: str | None, provider: str | None
) -> None:
    try:
        span.set_attribute("gen_ai.operation.name", "chat")
        if model_id:
            span.set_attribute("gen_ai.request.model", model_id)
        if provider:
            span.set_attribute("gen_ai.provider.name", provider)
    except Exception:  # pragma: no cover — defensive
        pass


def _annotate_model_response(
    span: Any,
    result: Any,
    *,
    model_id: str | None = None,
    provider: str | None = None,
) -> tuple[int | None, int | None]:
    """Best-effort: attach prompt/completion token counts when available."""
    input_tokens: int | None = None
    output_tokens: int | None = None
    try:
        # ModelResponse may be a dataclass with .result containing AIMessage
        msg: Any
        if isinstance(result, AIMessage):
            msg = result
        else:
            inner = getattr(result, "result", None)
            msg = inner[-1] if isinstance(inner, list) and inner else inner
        if msg is None:
            return None, None
        if provider:
            span.set_attribute("gen_ai.provider.name", provider)
        if model_id:
            span.set_attribute("gen_ai.request.model", model_id)
        response_model = getattr(msg, "response_metadata", {}) or {}
        if isinstance(response_model, dict):
            response_model = (
                response_model.get("model_name")
                or response_model.get("model")
                or response_model.get("model_id")
            )
        if not response_model:
            response_model = model_id
        if response_model:
            span.set_attribute("gen_ai.response.model", str(response_model))
        span.set_attribute("gen_ai.operation.name", "chat")
        usage = getattr(msg, "usage_metadata", None) or {}
        if isinstance(usage, dict):
            if (n := usage.get("input_tokens")) is not None:
                input_tokens = int(n)
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            if (n := usage.get("output_tokens")) is not None:
                output_tokens = int(n)
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
            if (n := usage.get("total_tokens")) is not None:
                span.set_attribute("gen_ai.usage.total_tokens", int(n))
        tool_calls = getattr(msg, "tool_calls", None) or []
        span.set_attribute("model.tool_calls", len(tool_calls))
    except Exception:  # pragma: no cover — defensive
        pass
    return input_tokens, output_tokens


def _annotate_tool_result(span: Any, result: Any) -> bool:
    errored = False
    try:
        if isinstance(result, ToolMessage):
            content = (
                result.content
                if isinstance(result.content, str)
                else repr(result.content)
            )
            span.set_attribute("tool.output.size", len(content))
            status = getattr(result, "status", None)
            if isinstance(status, str):
                span.set_attribute("tool.status", status)
                errored = status.lower() == "error"
            kwargs = getattr(result, "additional_kwargs", None) or {}
            if isinstance(kwargs, dict) and kwargs.get("error"):
                span.set_attribute("tool.error", True)
                errored = True
    except Exception:  # pragma: no cover — defensive
        pass
    return errored


__all__ = ["OtelSpanMiddleware"]
