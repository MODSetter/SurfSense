"""Handle the ``except Exception`` branch of a streaming flow.

Classifies the exception, records OpenTelemetry attributes, emits one terminal
error SSE frame and the trailing ``turn-status: idle`` + finish/done frames.

Used by both ``stream_new_chat`` and ``stream_resume_chat``; flow-specific bits
(label, span, BusyError tracking) are passed by the caller.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Iterator
from typing import Any, Literal

from app.agents.chat.multi_agent_chat.shared.errors import BusyError
from app.observability import metrics as ot_metrics, otel as ot
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.streaming.errors.classifier import classify_stream_exception
from app.tasks.chat.streaming.errors.emitter import emit_stream_terminal_error
from app.tasks.chat.streaming.flows.shared.first_frames import iter_final_frames
from app.tasks.chat.streaming.flows.shared.span import record_outcome_attrs

logger = logging.getLogger(__name__)


def handle_terminal_exception(
    exc: Exception,
    *,
    flow: Literal["new", "regenerate", "resume"],
    flow_label: str,
    log_prefix: str,
    streaming_service: VercelStreamingService,
    request_id: str | None,
    chat_id: int,
    search_space_id: int,
    user_id: str | None,
    chat_span: Any,
) -> tuple[Iterator[str], dict[str, Any]]:
    """Classify, log, and produce the SSE frames for a terminal exception.

    Returns ``(frame_iterator, summary)``. ``summary`` carries::

      - ``busy_error_raised``: bool — caller must skip the lock-release path
        when True (caller never acquired the busy mutex).
      - ``chat_outcome``: str  — span outcome attribute.
      - ``chat_error_category``: str — categorized error label for metrics.
    """
    busy_error_raised = isinstance(exc, BusyError)

    (
        error_kind,
        error_code,
        severity,
        is_expected,
        user_message,
        error_extra,
    ) = classify_stream_exception(exc, flow_label=flow_label)
    chat_outcome = error_code or error_kind or "error"
    chat_error_category = ot_metrics.categorize_exception(exc)
    record_outcome_attrs(
        chat_span,
        chat_outcome=chat_outcome,
        chat_error_category=chat_error_category,
    )
    with __suppress():
        ot.record_error(chat_span, exc)
    error_message = f"Error during {flow_label}: {exc!s}"
    # Match the original behavior: log full traceback via ``print`` so it lands
    # in stderr regardless of the logger config.
    print(f"[{log_prefix}] {error_message}")
    print(f"[{log_prefix}] Exception type: {type(exc).__name__}")
    print(f"[{log_prefix}] Traceback:\n{traceback.format_exc()}")

    def _iter_frames() -> Iterator[str]:
        if error_code == "TURN_CANCELLING":
            status_payload: dict[str, Any] = {"status": "cancelling"}
            if error_extra:
                status_payload.update(error_extra)
            yield streaming_service.format_data("turn-status", status_payload)
        else:
            yield streaming_service.format_data("turn-status", {"status": "busy"})

        yield emit_stream_terminal_error(
            streaming_service=streaming_service,
            flow=flow,
            request_id=request_id,
            thread_id=chat_id,
            search_space_id=search_space_id,
            user_id=user_id,
            message=user_message,
            error_kind=error_kind,
            error_code=error_code,
            severity=severity,
            is_expected=is_expected,
            extra=error_extra,
        )
        yield from iter_final_frames(streaming_service)

    return (
        _iter_frames(),
        {
            "busy_error_raised": busy_error_raised,
            "chat_outcome": chat_outcome,
            "chat_error_category": chat_error_category,
        },
    )


def __suppress():
    """Local single-use ``contextlib.suppress(Exception)`` factory.

    Inlined here so callers don't import ``contextlib`` just for the
    ``record_error`` call site.
    """
    import contextlib

    return contextlib.suppress(Exception)
