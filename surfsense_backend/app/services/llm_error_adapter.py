"""Normalize provider/LLM exceptions into low-cardinality product categories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class LLMErrorCategory(StrEnum):
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    BAD_GATEWAY = "bad_gateway"
    CONNECTION_FAILED = "connection_failed"
    AUTH_FAILED = "auth_failed"
    PERMISSION_DENIED = "permission_denied"
    MODEL_NOT_FOUND = "model_not_found"
    BAD_REQUEST = "bad_request"
    CONTEXT_LIMIT = "context_limit"
    INSUFFICIENT_MEMORY = "insufficient_memory"
    RESPONSE_INVALID = "response_invalid"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LLMErrorAdaptation:
    category: LLMErrorCategory
    retryable: bool
    user_message: str
    provider_status_code: int | None = None
    provider_error_type: str | None = None


_CATEGORY_MESSAGES: dict[LLMErrorCategory, str] = {
    LLMErrorCategory.RATE_LIMITED: "LLM rate limit exceeded. Will retry on next sync.",
    LLMErrorCategory.TIMEOUT: "LLM request timed out. Will retry on next sync.",
    LLMErrorCategory.PROVIDER_UNAVAILABLE: "LLM service temporarily unavailable. Will retry on next sync.",
    LLMErrorCategory.BAD_GATEWAY: "LLM gateway error. Will retry on next sync.",
    LLMErrorCategory.CONNECTION_FAILED: "Could not reach the LLM service. Check network connectivity.",
    LLMErrorCategory.AUTH_FAILED: "LLM authentication failed. Check your API key.",
    LLMErrorCategory.PERMISSION_DENIED: "LLM request denied. Check your account permissions.",
    LLMErrorCategory.MODEL_NOT_FOUND: "Model not found. Check your model configuration.",
    LLMErrorCategory.BAD_REQUEST: "LLM rejected the request. Document content may be invalid.",
    LLMErrorCategory.CONTEXT_LIMIT: "Document exceeds the LLM context window even after optimization.",
    LLMErrorCategory.INSUFFICIENT_MEMORY: "The LLM host ran out of memory loading this model. Free memory on the host or use a smaller model.",
    LLMErrorCategory.RESPONSE_INVALID: "LLM returned an invalid response.",
    LLMErrorCategory.SERVER_ERROR: "LLM internal server error. Will retry on next sync.",
    LLMErrorCategory.UNKNOWN: "Something went wrong when calling the LLM.",
}

_RETRYABLE_CATEGORIES = {
    LLMErrorCategory.RATE_LIMITED,
    LLMErrorCategory.TIMEOUT,
    LLMErrorCategory.PROVIDER_UNAVAILABLE,
    LLMErrorCategory.BAD_GATEWAY,
    LLMErrorCategory.CONNECTION_FAILED,
    LLMErrorCategory.SERVER_ERROR,
}

_CLASS_NAME_MAP: tuple[tuple[LLMErrorCategory, tuple[str, ...]], ...] = (
    (
        LLMErrorCategory.RATE_LIMITED,
        ("RateLimitError", "TooManyRequests", "TooManyRequestsError"),
    ),
    (LLMErrorCategory.TIMEOUT, ("Timeout", "APITimeoutError", "TimeoutException")),
    (
        LLMErrorCategory.PROVIDER_UNAVAILABLE,
        ("ServiceUnavailableError", "ServiceUnavailable"),
    ),
    (
        LLMErrorCategory.BAD_GATEWAY,
        ("BadGatewayError", "GatewayTimeoutError"),
    ),
    (
        LLMErrorCategory.CONNECTION_FAILED,
        ("APIConnectionError", "ConnectError", "ConnectTimeout", "ReadTimeout"),
    ),
    (
        LLMErrorCategory.AUTH_FAILED,
        ("AuthenticationError", "InvalidApiKey", "InvalidAPIKey", "InvalidApiKeyError"),
    ),
    (LLMErrorCategory.PERMISSION_DENIED, ("PermissionDeniedError", "ForbiddenError")),
    (LLMErrorCategory.MODEL_NOT_FOUND, ("NotFoundError", "ModelNotFoundError")),
    (
        LLMErrorCategory.CONTEXT_LIMIT,
        ("ContextWindowExceeded", "ContextOverflow", "ContextLimit"),
    ),
    (
        LLMErrorCategory.RESPONSE_INVALID,
        ("APIResponseValidationError", "ResponseValidationError"),
    ),
    (
        LLMErrorCategory.BAD_REQUEST,
        ("BadRequestError", "InvalidRequestError", "UnprocessableEntityError"),
    ),
    (LLMErrorCategory.SERVER_ERROR, ("InternalServerError",)),
)

# The first block is Ollama's own ``outOfMemorySubstrings`` from ``llm/status.go``:
# the list they scrape subprocess logs with, so matching it keeps us in step with
# what the runtime itself calls an OOM. The last two are returned directly rather
# than logged, so they are absent from that list -- the pre-flight "does not fit"
# check, which is ``ErrLoadRequiredFull`` on current Ollama and was a formatted
# "requires more system memory" through v0.9.
_INSUFFICIENT_MEMORY_HINTS = (
    "out of memory",
    "out of device memory",
    "cudamalloc failed",
    "hipmalloc failed",
    "failed to allocate",
    "allocation failed",
    "not enough memory",
    "insufficient memory",
    "vk_error_out_of_device_memory",
    "erroroutofmemory",
    "unable to load full model on gpu",
    "requires more system memory",
)


def _parse_error_payload(message: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    candidate_starts = [-1]
    candidate_starts.extend(index for index, char in enumerate(message) if char == "{")
    for start in candidate_starts[:21]:
        candidate = message if start == -1 else message[start:]
        try:
            parsed, _ = decoder.raw_decode(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (TypeError, ValueError):
            continue
    return None


def _class_names(exc: BaseException) -> tuple[str, ...]:
    return tuple(cls.__name__ for cls in type(exc).__mro__)


def _category_from_class_name(exc: BaseException) -> LLMErrorCategory | None:
    names = _class_names(exc)
    for category, hints in _CLASS_NAME_MAP:
        if any(any(hint in name for hint in hints) for name in names):
            return category
    return None


def _extract_provider_status_code(parsed: dict[str, Any] | None) -> int | None:
    if not isinstance(parsed, dict):
        return None
    candidates: list[Any] = [parsed.get("code"), parsed.get("status")]
    nested = parsed.get("error")
    if isinstance(nested, dict):
        candidates.extend([nested.get("code"), nested.get("status")])
    for value in candidates:
        try:
            if value is None:
                continue
            return int(value)
        except Exception:
            continue
    return None


def _extract_provider_error_type(parsed: dict[str, Any] | None) -> str | None:
    if not isinstance(parsed, dict):
        return None
    candidates: list[Any] = [parsed.get("type")]
    nested = parsed.get("error")
    if isinstance(nested, dict):
        candidates.append(nested.get("type"))
    for value in candidates:
        if isinstance(value, str) and value:
            return value
    return None


def _category_from_provider_payload(
    status_code: int | None,
    provider_error_type: str | None,
) -> LLMErrorCategory | None:
    normalized_type = (provider_error_type or "").lower()
    if normalized_type == "rate_limit_error":
        return LLMErrorCategory.RATE_LIMITED
    if normalized_type in {
        "authentication_error",
        "invalid_api_key",
        "invalid_api_key_error",
    }:
        return LLMErrorCategory.AUTH_FAILED
    if normalized_type in {"permission_denied", "forbidden"}:
        return LLMErrorCategory.PERMISSION_DENIED
    if normalized_type in {"not_found_error", "model_not_found"}:
        return LLMErrorCategory.MODEL_NOT_FOUND
    if normalized_type in {
        "context_length_exceeded",
        "context_window_exceeded",
        "exceed_context_size_error",
    }:
        return LLMErrorCategory.CONTEXT_LIMIT
    if status_code == 429:
        return LLMErrorCategory.RATE_LIMITED
    if status_code == 401:
        return LLMErrorCategory.AUTH_FAILED
    if status_code == 403:
        return LLMErrorCategory.PERMISSION_DENIED
    if status_code == 404:
        return LLMErrorCategory.MODEL_NOT_FOUND
    if status_code in (400, 422):
        return LLMErrorCategory.BAD_REQUEST
    if status_code in (502, 504):
        return LLMErrorCategory.BAD_GATEWAY
    if status_code == 503:
        return LLMErrorCategory.PROVIDER_UNAVAILABLE
    if status_code is not None and status_code >= 500:
        return LLMErrorCategory.SERVER_ERROR
    return None


def _category_from_message(raw: str) -> LLMErrorCategory | None:
    lowered = raw.lower()
    # Checked first: a runtime that fails to reserve the KV cache reports the
    # requested ``n_ctx`` alongside the allocation failure, which would otherwise
    # read as a context-limit error and tell the user to shrink a prompt that was
    # never the problem.
    if any(hint in lowered for hint in _INSUFFICIENT_MEMORY_HINTS):
        return LLMErrorCategory.INSUFFICIENT_MEMORY
    if any(
        hint in lowered
        for hint in ("rate limit", "rate-limited", "temporarily rate-limited")
    ):
        return LLMErrorCategory.RATE_LIMITED
    if any(
        hint in lowered
        for hint in (
            "invalid api key",
            "invalid_api_key",
            "authentication",
            "unauthorized",
            "user not found",
            "api key is expired",
            "expired api key",
        )
    ):
        return LLMErrorCategory.AUTH_FAILED
    if "forbidden" in lowered or "permission denied" in lowered:
        return LLMErrorCategory.PERMISSION_DENIED
    if "model not found" in lowered:
        return LLMErrorCategory.MODEL_NOT_FOUND
    if any(
        hint in lowered
        for hint in (
            "context length",
            "context window",
            "maximum context",
            "too many tokens",
            "available context size",
            "n_ctx",
        )
    ):
        return LLMErrorCategory.CONTEXT_LIMIT
    return None


def _exception_chain(exc: BaseException, max_depth: int = 5) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and len(chain) < max_depth and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def adapt_llm_exception(exc: BaseException) -> LLMErrorAdaptation:
    entries: list[tuple[BaseException, str, int | None, str | None]] = []
    for current in _exception_chain(exc):
        raw = str(current)
        parsed = _parse_error_payload(raw)
        entries.append(
            (
                current,
                raw,
                _extract_provider_status_code(parsed),
                _extract_provider_error_type(parsed),
            )
        )

    category: LLMErrorCategory | None = None
    matched_status: int | None = None
    matched_type: str | None = None

    # Provider semantics across the entire wrapper chain must win over generic
    # HTTP statuses and wrapper class names.
    for _, _, status_code, provider_error_type in entries:
        if provider_error_type:
            semantic = _category_from_provider_payload(None, provider_error_type)
            if semantic is not None:
                category = semantic
                matched_status = status_code
                matched_type = provider_error_type
                break
    if category is None:
        for _, raw, status_code, provider_error_type in entries:
            semantic = _category_from_message(raw)
            if semantic is not None:
                category = semantic
                matched_status = status_code
                matched_type = provider_error_type
                break
    if category is None:
        for _, _, status_code, provider_error_type in entries:
            status_category = _category_from_provider_payload(
                status_code, provider_error_type
            )
            if status_category is not None:
                category = status_category
                matched_status = status_code
                matched_type = provider_error_type
                break
    if category is None:
        for current, _, status_code, provider_error_type in entries:
            class_category = _category_from_class_name(current)
            if class_category is not None:
                category = class_category
                matched_status = status_code
                matched_type = provider_error_type
                break

    category = category or LLMErrorCategory.UNKNOWN
    return LLMErrorAdaptation(
        category=category,
        retryable=category in _RETRYABLE_CATEGORIES,
        user_message=_CATEGORY_MESSAGES[category],
        provider_status_code=matched_status,
        provider_error_type=matched_type,
    )


def llm_error_message(exc: BaseException) -> str:
    return adapt_llm_exception(exc).user_message
