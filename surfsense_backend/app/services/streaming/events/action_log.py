"""Action-log events relayed from ``ActionLogMiddleware`` custom dispatches."""

from __future__ import annotations

from typing import Any

from ..emitter import Emitter
from .data import format_data


def format_action_log(
    payload: dict[str, Any],
    *,
    emitter: Emitter | None = None,
) -> str:
    return format_data("action-log", payload, emitter=emitter)


def format_action_log_updated(
    payload: dict[str, Any],
    *,
    emitter: Emitter | None = None,
) -> str:
    return format_data("action-log-updated", payload, emitter=emitter)
