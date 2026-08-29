"""Chat-turn telemetry: request span + duration/outcome metrics."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.observability.signals import metrics as m
from app.observability.signals.tracing import span


def chat_request_span(
    *,
    chat_id: int | None = None,
    workspace_id: int | None = None,
    flow: str | None = None,
    request_id: str | None = None,
    turn_id: str | None = None,
    filesystem_mode: str | None = None,
    client_platform: str | None = None,
    agent_mode: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Parent span for a single streamed chat or resume turn."""
    attrs: dict[str, Any] = {}
    if chat_id is not None:
        attrs["chat.id"] = int(chat_id)
    if workspace_id is not None:
        attrs["workspace.id"] = int(workspace_id)
    if flow:
        attrs["chat.flow"] = flow
    if request_id:
        attrs["request.id"] = request_id
    if turn_id:
        attrs["turn.id"] = turn_id
    if filesystem_mode:
        attrs["filesystem.mode"] = filesystem_mode
    if client_platform:
        attrs["client.platform"] = client_platform
    if agent_mode:
        attrs["agent.mode"] = agent_mode
    if extra:
        attrs.update(extra)
    return span("chat.request", attributes=attrs)


@lru_cache(maxsize=1)
def _chat_request_duration():
    return m.get_meter().create_histogram(
        "surfsense.chat.request.duration",
        unit="ms",
        description="Duration of SurfSense streamed chat requests.",
    )


@lru_cache(maxsize=1)
def _chat_request_outcome():
    return m.get_meter().create_counter(
        "surfsense.chat.request.outcome",
        description="Count of SurfSense chat request outcomes.",
    )


def record_chat_request_duration(
    duration_ms: float, *, flow: str, outcome: str, agent_mode: str | None = None
) -> None:
    m.record(
        _chat_request_duration(),
        duration_ms,
        {"chat.flow": flow, "outcome": outcome, "agent.mode": agent_mode},
    )


def record_chat_request_outcome(
    *,
    flow: str,
    outcome: str,
    agent_mode: str | None = None,
    error_category: str | None = None,
) -> None:
    m.add(
        _chat_request_outcome(),
        1,
        m.attrs_with_error_category(
            {"chat.flow": flow, "outcome": outcome, "agent.mode": agent_mode},
            error_category,
        ),
    )
