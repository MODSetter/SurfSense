"""Classify stream exceptions for logging and client error payloads."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal

from app.agents.chat.multi_agent_chat.main_agent.middleware.busy_mutex import (
    get_cancel_state,
    is_cancel_requested,
)
from app.agents.chat.runtime.errors import BusyError
from app.services.llm_error_adapter import LLMErrorCategory, adapt_llm_exception

TURN_CANCELLING_INITIAL_DELAY_MS = 200
TURN_CANCELLING_BACKOFF_FACTOR = 2
TURN_CANCELLING_MAX_DELAY_MS = 1500


def compute_turn_cancelling_retry_delay(attempt: int) -> int:
    if attempt < 1:
        attempt = 1
    delay = TURN_CANCELLING_INITIAL_DELAY_MS * (
        TURN_CANCELLING_BACKOFF_FACTOR ** (attempt - 1)
    )
    return min(delay, TURN_CANCELLING_MAX_DELAY_MS)


def log_chat_stream_error(
    *,
    flow: Literal["new", "resume", "regenerate"],
    error_kind: str,
    error_code: str | None,
    severity: Literal["info", "warn", "error"],
    is_expected: bool,
    request_id: str | None,
    thread_id: int | None,
    search_space_id: int | None,
    user_id: str | None,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "event": "chat_stream_error",
        "flow": flow,
        "error_kind": error_kind,
        "error_code": error_code,
        "severity": severity,
        "is_expected": is_expected,
        "request_id": request_id or "unknown",
        "thread_id": thread_id,
        "search_space_id": search_space_id,
        "user_id": user_id,
        "message": message,
    }
    if extra:
        payload.update(extra)

    logger = logging.getLogger(__name__)
    rendered = json.dumps(payload, ensure_ascii=False)
    if severity == "error":
        logger.error("[chat_stream_error] %s", rendered)
    elif severity == "warn":
        logger.warning("[chat_stream_error] %s", rendered)
    else:
        logger.info("[chat_stream_error] %s", rendered)


def _parse_error_payload(message: str) -> dict[str, Any] | None:
    candidates = [message]
    first_brace_idx = message.find("{")
    if first_brace_idx >= 0:
        candidates.append(message[first_brace_idx:])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _extract_provider_error_code(parsed: dict[str, Any] | None) -> int | None:
    if not isinstance(parsed, dict):
        return None
    candidates: list[Any] = [parsed.get("code")]
    nested = parsed.get("error")
    if isinstance(nested, dict):
        candidates.append(nested.get("code"))
    for value in candidates:
        try:
            if value is None:
                continue
            return int(value)
        except Exception:
            continue
    return None


def is_provider_rate_limited(exc: BaseException) -> bool:
    """Return True if the exception looks like an upstream HTTP 429 / rate limit."""
    if adapt_llm_exception(exc).category is LLMErrorCategory.RATE_LIMITED:
        return True

    raw = str(exc)
    lowered = raw.lower()
    if "ratelimit" in type(exc).__name__.lower():
        return True
    parsed = _parse_error_payload(raw)
    provider_code = _extract_provider_error_code(parsed)
    if provider_code == 429:
        return True

    provider_error_type = ""
    if parsed:
        top_type = parsed.get("type")
        if isinstance(top_type, str):
            provider_error_type = top_type.lower()
        nested = parsed.get("error")
        if isinstance(nested, dict):
            nested_type = nested.get("type")
            if isinstance(nested_type, str):
                provider_error_type = nested_type.lower()
    if provider_error_type == "rate_limit_error":
        return True

    return (
        "rate limited" in lowered
        or "rate-limited" in lowered
        or "temporarily rate-limited upstream" in lowered
    )


def _provider_error_extra(adapted: Any) -> dict[str, Any] | None:
    extra: dict[str, Any] = {"provider_error_category": adapted.category.value}
    if adapted.provider_status_code is not None:
        extra["provider_status_code"] = adapted.provider_status_code
    if adapted.provider_error_type:
        extra["provider_error_type"] = adapted.provider_error_type
    return extra


def _classify_provider_exception(
    exc: Exception,
) -> (
    tuple[str, str, Literal["info", "warn", "error"], bool, str, dict[str, Any] | None]
    | None
):
    adapted = adapt_llm_exception(exc)

    if adapted.category is LLMErrorCategory.RATE_LIMITED:
        return (
            "rate_limited",
            "RATE_LIMITED",
            "warn",
            True,
            "This model is temporarily rate-limited. Please try again in a few seconds or switch models.",
            _provider_error_extra(adapted),
        )

    if adapted.category in {
        LLMErrorCategory.AUTH_FAILED,
        LLMErrorCategory.PERMISSION_DENIED,
    }:
        return (
            "model_auth_failed",
            "MODEL_AUTH_FAILED",
            "warn",
            True,
            "This model's API key is invalid or expired. Switch models, or update the API key.",
            _provider_error_extra(adapted),
        )

    if adapted.category is LLMErrorCategory.MODEL_NOT_FOUND:
        return (
            "model_not_found",
            "MODEL_NOT_FOUND",
            "warn",
            True,
            "The selected model is unavailable or no longer exists. Switch to another model and try again.",
            _provider_error_extra(adapted),
        )

    if adapted.category is LLMErrorCategory.CONTEXT_LIMIT:
        return (
            "model_context_limit",
            "MODEL_CONTEXT_LIMIT",
            "warn",
            True,
            "This request is too large for the selected model. Try a model with a larger context window or reduce the input.",
            _provider_error_extra(adapted),
        )

    if adapted.category in {
        LLMErrorCategory.TIMEOUT,
        LLMErrorCategory.PROVIDER_UNAVAILABLE,
        LLMErrorCategory.BAD_GATEWAY,
        LLMErrorCategory.CONNECTION_FAILED,
        LLMErrorCategory.SERVER_ERROR,
    }:
        return (
            "model_provider_unavailable",
            "MODEL_PROVIDER_UNAVAILABLE",
            "warn",
            True,
            "The selected model provider is temporarily unavailable. Please try again or switch models.",
            _provider_error_extra(adapted),
        )

    return None


def classify_stream_exception(
    exc: Exception,
    *,
    flow_label: str,
) -> tuple[
    str, str, Literal["info", "warn", "error"], bool, str, dict[str, Any] | None
]:
    """Return kind, code, severity, expected flag, message, and optional extra dict."""
    raw = str(exc)
    if isinstance(exc, BusyError) or "Thread is busy with another request" in raw:
        busy_thread_id = str(exc.request_id) if isinstance(exc, BusyError) else None
        if busy_thread_id and is_cancel_requested(busy_thread_id):
            cancel_state = get_cancel_state(busy_thread_id)
            attempt = cancel_state[0] if cancel_state else 1
            retry_after_ms = compute_turn_cancelling_retry_delay(attempt)
            retry_after_at = int(time.time() * 1000) + retry_after_ms
            return (
                "thread_busy",
                "TURN_CANCELLING",
                "info",
                True,
                "A previous response is still stopping. Please try again in a moment.",
                {
                    "retry_after_ms": retry_after_ms,
                    "retry_after_at": retry_after_at,
                },
            )
        return (
            "thread_busy",
            "THREAD_BUSY",
            "warn",
            True,
            "Another response is still finishing for this thread. Please try again in a moment.",
            None,
        )

    provider_classification = _classify_provider_exception(exc)
    if provider_classification is not None:
        return provider_classification

    return (
        "server_error",
        "SERVER_ERROR",
        "error",
        False,
        f"Error during {flow_label}: {raw}",
        None,
    )
