"""Agent telemetry: LLM/tool/subagent spans + GenAI metrics.

Span names stay low-cardinality (``model.call``, not ``model.call.<model>``);
identifiers live in attributes so dashboards aggregate. GenAI attribute keys
come from :mod:`app.observability.core.semconv`.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from app.observability.core import semconv
from app.observability.signals import metrics as m
from app.observability.signals.tracing import SpanKind, span

# Set while a ``model.call`` span is open so the LLM-client chokepoint can defer
# to the agent middleware and avoid double-spanning the same call.
_model_call_active: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "surfsense_model_call_active", default=False
)


def model_call_active() -> bool:
    """True when a ``model.call`` span is already open on this context."""
    return _model_call_active.get()


def tool_call_span(
    tool_name: str,
    *,
    input_size: int | None = None,
    extra: dict[str, Any] | None = None,
):
    attrs: dict[str, Any] = {"tool.name": tool_name}
    if input_size is not None:
        attrs["tool.input.size"] = int(input_size)
    if extra:
        attrs.update(extra)
    return span("tool.call", attributes=attrs)


@contextmanager
def model_call_span(
    *,
    model_id: str | None = None,
    provider: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around one LLM astream/ainvoke call (SpanKind.CLIENT per GenAI).

    Marks the context (:func:`model_call_active`) so nested LLM-client
    instrumentation defers to this span instead of emitting its own.
    """
    attrs: dict[str, Any] = {
        semconv.GEN_AI_OPERATION_NAME: semconv.GEN_AI_OPERATION_CHAT
    }
    if model_id:
        attrs["model.id"] = model_id
        attrs[semconv.GEN_AI_REQUEST_MODEL] = model_id
    if provider:
        attrs["model.provider"] = provider
        attrs[semconv.GEN_AI_PROVIDER_NAME] = provider
    if extra:
        attrs.update(extra)
    token = _model_call_active.set(True)
    try:
        with span(
            "model.call",
            kind=SpanKind.CLIENT if SpanKind is not None else None,
            attributes=attrs,
        ) as sp:
            yield sp
    finally:
        _model_call_active.reset(token)


def subagent_invoke_span(
    *,
    subagent_type: str,
    path: str | None = None,
    extra: dict[str, Any] | None = None,
):
    attrs: dict[str, Any] = {"subagent.type": subagent_type}
    if path:
        attrs["subagent.path"] = path
    if extra:
        attrs.update(extra)
    return span("subagent.invoke", attributes=attrs)


def compaction_span(
    *,
    reason: str | None = None,
    messages_in: int | None = None,
    extra: dict[str, Any] | None = None,
):
    attrs: dict[str, Any] = {}
    if reason:
        attrs["compaction.reason"] = reason
    if messages_in is not None:
        attrs["compaction.messages.in"] = int(messages_in)
    if extra:
        attrs.update(extra)
    return span("compaction.run", attributes=attrs)


def interrupt_span(*, interrupt_type: str, extra: dict[str, Any] | None = None):
    attrs: dict[str, Any] = {"interrupt.type": interrupt_type}
    if extra:
        attrs.update(extra)
    return span("interrupt.raised", attributes=attrs)


def permission_asked_span(
    *,
    permission: str,
    pattern: str | None = None,
    extra: dict[str, Any] | None = None,
):
    attrs: dict[str, Any] = {"permission.permission": permission}
    if pattern:
        attrs["permission.pattern"] = pattern
    if extra:
        attrs.update(extra)
    return span("permission.asked", attributes=attrs)


@lru_cache(maxsize=1)
def _model_call_duration():
    return m.get_meter().create_histogram(
        "surfsense.model.call.duration",
        unit="ms",
        description="Duration of SurfSense LLM model calls.",
    )


@lru_cache(maxsize=1)
def _model_token_usage():
    return m.get_meter().create_histogram(
        semconv.METRIC_GEN_AI_TOKEN_USAGE,
        unit="{token}",
        description="Token usage reported by GenAI model responses.",
    )


@lru_cache(maxsize=1)
def _tool_call_duration():
    return m.get_meter().create_histogram(
        "surfsense.tool.call.duration",
        unit="ms",
        description="Duration of SurfSense agent tool calls.",
    )


@lru_cache(maxsize=1)
def _tool_call_errors():
    return m.get_meter().create_counter(
        "surfsense.tool.call.errors",
        description="Count of SurfSense agent tool call errors.",
    )


@lru_cache(maxsize=1)
def _compaction_runs():
    return m.get_meter().create_counter(
        "surfsense.compaction.runs",
        description="Count of SurfSense conversation compaction runs.",
    )


@lru_cache(maxsize=1)
def _permission_asks():
    return m.get_meter().create_counter(
        "surfsense.permission.asks",
        description="Count of SurfSense permission asks.",
    )


@lru_cache(maxsize=1)
def _interrupts():
    return m.get_meter().create_counter(
        "surfsense.interrupt.raised",
        description="Count of SurfSense interrupts raised.",
    )


@lru_cache(maxsize=1)
def _subagent_invoke_duration():
    return m.get_meter().create_histogram(
        "surfsense.subagent.invoke.duration",
        unit="ms",
        description="Duration of SurfSense subagent invocations.",
    )


@lru_cache(maxsize=1)
def _subagent_invoke_outcome():
    return m.get_meter().create_counter(
        "surfsense.subagent.invoke.outcome",
        description="Count of SurfSense subagent invocation outcomes.",
    )


def record_model_call_duration(
    duration_ms: float, *, model: str | None, provider: str | None
) -> None:
    m.record(
        _model_call_duration(),
        duration_ms,
        {
            semconv.GEN_AI_REQUEST_MODEL: model,
            semconv.GEN_AI_PROVIDER_NAME: provider,
        },
    )


def record_model_token_usage(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    model: str | None,
    provider: str | None,
) -> None:
    base = {
        semconv.GEN_AI_REQUEST_MODEL: model,
        semconv.GEN_AI_PROVIDER_NAME: provider,
        semconv.GEN_AI_OPERATION_NAME: semconv.GEN_AI_OPERATION_CHAT,
    }
    if input_tokens is not None:
        m.record(
            _model_token_usage(),
            int(input_tokens),
            {**base, semconv.GEN_AI_TOKEN_TYPE: "input"},
        )
    if output_tokens is not None:
        m.record(
            _model_token_usage(),
            int(output_tokens),
            {**base, semconv.GEN_AI_TOKEN_TYPE: "output"},
        )


def record_tool_call_duration(duration_ms: float, *, tool_name: str) -> None:
    m.record(_tool_call_duration(), duration_ms, {"tool.name": tool_name})


def record_tool_call_error(*, tool_name: str) -> None:
    m.add(_tool_call_errors(), 1, {"tool.name": tool_name})


def record_compaction_run(*, reason: str | None) -> None:
    m.add(_compaction_runs(), 1, {"compaction.reason": reason or "unknown"})


def record_permission_ask(*, permission: str) -> None:
    m.add(_permission_asks(), 1, {"permission.permission": permission})


def record_interrupt(*, interrupt_type: str) -> None:
    m.add(_interrupts(), 1, {"interrupt.type": interrupt_type})


def record_subagent_invoke_duration(
    duration_ms: float, *, subagent_type: str, path: str | None, outcome: str
) -> None:
    m.record(
        _subagent_invoke_duration(),
        duration_ms,
        {
            "subagent.type": subagent_type,
            "subagent.path": path or "unknown",
            "outcome": outcome,
        },
    )


def record_subagent_invoke_outcome(
    *, subagent_type: str, path: str | None, outcome: str
) -> None:
    m.add(
        _subagent_invoke_outcome(),
        1,
        {
            "subagent.type": subagent_type,
            "subagent.path": path or "unknown",
            "outcome": outcome,
        },
    )
