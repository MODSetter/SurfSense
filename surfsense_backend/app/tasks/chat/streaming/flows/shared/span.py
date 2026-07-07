"""OpenTelemetry chat-request span wrapper for streaming flows."""

from __future__ import annotations

import contextlib
import sys
from typing import Any, Literal

from app.observability import metrics as ot_metrics, otel as ot


def open_chat_request_span(
    *,
    chat_id: int,
    workspace_id: int,
    flow: Literal["new", "regenerate", "resume"],
    request_id: str | None,
    turn_id: str,
    filesystem_mode: str,
    client_platform: str,
    agent_mode: str,
) -> tuple[Any, Any]:
    """Open the per-request span; returns ``(span_cm, span)`` for finally-close."""
    span_cm = ot.chat_request_span(
        chat_id=chat_id,
        workspace_id=workspace_id,
        flow=flow,
        request_id=request_id,
        turn_id=turn_id,
        filesystem_mode=filesystem_mode,
        client_platform=client_platform,
        agent_mode=agent_mode,
    )
    span = span_cm.__enter__()
    return span_cm, span


def set_agent_mode(span: Any, agent_mode: str) -> None:
    """Tag the span with the resolved agent mode (single / multi)."""
    with contextlib.suppress(Exception):
        span.set_attribute("agent.mode", agent_mode)


def close_chat_request_span(
    *,
    span_cm: Any,
    span: Any,
    chat_outcome: str,
    chat_agent_mode: str,
    flow: Literal["new", "regenerate", "resume"],
    chat_error_category: str | None,
    duration_seconds: float,
) -> None:
    """Record metrics + close the span. Swallows errors (finally-block context)."""
    with contextlib.suppress(Exception):
        span.set_attribute("chat.outcome", chat_outcome)
        ot_metrics.record_chat_request_duration(
            duration_seconds * 1000,
            flow=flow,
            outcome=chat_outcome,
            agent_mode=chat_agent_mode,
        )
        ot_metrics.record_chat_request_outcome(
            flow=flow,
            outcome=chat_outcome,
            agent_mode=chat_agent_mode,
            error_category=chat_error_category,
        )
    span_cm.__exit__(*sys.exc_info())


def record_outcome_attrs(
    span: Any, *, chat_outcome: str, chat_error_category: str | None
) -> None:
    """Stamp outcome + error.category on the span (used in the except branch)."""
    with contextlib.suppress(Exception):
        span.set_attribute("chat.outcome", chat_outcome)
        if chat_error_category is not None:
            span.set_attribute("error.category", chat_error_category)
